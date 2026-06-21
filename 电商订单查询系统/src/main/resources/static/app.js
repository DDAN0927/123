// ========== 全局数据 ==========
let users = [];
let products = [];

// ========== 工具函数 ==========
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2800);
}

function formatPrice(price) {
    return Number(price).toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function getStockLevel(stock) {
    if (stock <= 0) return { class: 'out', text: '已售罄' };
    if (stock <= 20) return { class: 'low', text: `库存紧张 (${stock})` };
    if (stock <= 100) return { class: 'mid', text: `库存适中 (${stock})` };
    return { class: 'high', text: `库存充足 (${stock})` };
}

// ========== 数据加载 ==========
async function loadData() {
    try {
        const [usersRes, productsRes] = await Promise.all([
            fetch('/api/users'),
            fetch('/api/products')
        ]);

        users = await usersRes.json();
        products = await productsRes.json();

        renderStats();
        renderProducts();
        renderFormOptions();
    } catch (err) {
        console.error('加载数据失败:', err);
        showToast('数据加载失败，请刷新页面重试', 'error');
    }
}

// ========== 渲染统计 ==========
function renderStats() {
    const totalStock = products.reduce((sum, p) => sum + (p.stock || 0), 0);
    animateNumber('userCount', users.length);
    animateNumber('productCount', products.length);
    animateNumber('totalStock', totalStock);
}

function animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 30));
    const timer = setInterval(() => {
        current += step;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        el.textContent = current;
    }, 30);
}

// ========== 渲染商品卡片 ==========
function renderProducts() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;

    grid.innerHTML = products.map(p => {
        const stockInfo = getStockLevel(p.stock);
        return `
            <div class="product-card">
                <span class="product-id">商品 #${p.id}</span>
                <div class="product-name">${p.productName}</div>
                <div class="product-meta">
                    <div class="product-price">
                        <span class="currency">¥</span>${formatPrice(p.price)}
                    </div>
                    <span class="stock-tag ${stockInfo.class}">${stockInfo.text}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ========== 渲染下拉选项 ==========
function renderFormOptions() {
    const userSelect = document.getElementById('userId');
    const productSelect = document.getElementById('productId');

    userSelect.innerHTML = '<option value="">请选择用户</option>' +
        users.map(u => `<option value="${u.id}">${u.username} (${u.phone})</option>`).join('');

    productSelect.innerHTML = '<option value="">请选择商品</option>' +
        products.map(p => `<option value="${p.id}">${p.productName} - ¥${formatPrice(p.price)}</option>`).join('');
}

// ========== 商品选择时显示库存提示 ==========
function updateStockHint() {
    const productId = Number(document.getElementById('productId').value);
    const quantity = Number(document.getElementById('quantity').value) || 0;
    const hint = document.getElementById('stockHint');

    const product = products.find(p => p.id === productId);
    if (!product) {
        hint.textContent = '';
        return;
    }

    hint.textContent = `当前库存: ${product.stock} 件`;
    if (product.stock === 0) {
        hint.textContent += ' - 该商品已售罄';
    }

    // 动态调整数量上限
    const qtyInput = document.getElementById('quantity');
    if (product.stock > 0) {
        qtyInput.max = product.stock;
    } else {
        qtyInput.max = 1;
    }
}

// ========== 创建订单 ==========
async function createOrder(e) {
    e.preventDefault();

    const userId = document.getElementById('userId').value;
    const productId = document.getElementById('productId').value;
    const quantity = document.getElementById('quantity').value;

    if (!userId || !productId || !quantity) {
        showToast('请选择用户、商品并填写数量', 'error');
        return;
    }

    const product = products.find(p => p.id === Number(productId));
    if (product && Number(quantity) > product.stock) {
        showToast(`库存不足！当前库存仅 ${product.stock} 件`, 'error');
        return;
    }

    const submitBtn = document.getElementById('submitBtn');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳ 处理中...</span>';

    try {
        const res = await fetch(`/api/orders?userId=${userId}&productId=${productId}&quantity=${quantity}`, {
            method: 'POST'
        });
        const result = await res.json();

        const resultArea = document.getElementById('createResult');

        if (result.code === 200 && result.data) {
            const data = result.data;
            resultArea.style.display = 'block';
            resultArea.innerHTML = `
                <div class="result-success">✅ 订单创建成功！</div>
                <div class="order-detail">
                    <div class="order-header">
                        <span class="order-id">订单编号：<strong>#${data.orderId}</strong></span>
                        <span class="order-status">已下单</span>
                    </div>
                    <div class="order-info-grid">
                        <div class="info-item">
                            <div class="info-label">👤 用户</div>
                            <div class="info-value">${data.userName}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">📦 商品</div>
                            <div class="info-value">${data.productName}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">🔢 数量</div>
                            <div class="info-value">${data.quantity} 件</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">💰 总价</div>
                            <div class="info-value price"><span class="currency">¥</span>${formatPrice(data.totalPrice)}</div>
                        </div>
                        <div class="info-item full">
                            <div class="info-label">🕐 下单时间</div>
                            <div class="info-value">${data.orderTime}</div>
                        </div>
                    </div>
                </div>
            `;
            showToast('订单创建成功！', 'success');

            // 刷新商品数据
            setTimeout(() => {
                loadProductDataOnly();
            }, 500);
        } else {
            resultArea.style.display = 'block';
            resultArea.innerHTML = `<div class="result-error">❌ ${result.message || '下单失败'}</div>`;
            showToast(result.message || '下单失败', 'error');
        }
    } catch (err) {
        console.error(err);
        const resultArea = document.getElementById('createResult');
        resultArea.style.display = 'block';
        resultArea.innerHTML = `<div class="result-error">❌ 网络异常，请稍后重试</div>`;
        showToast('网络异常', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// 仅刷新商品数据，不影响选择器
async function loadProductDataOnly() {
    try {
        const res = await fetch('/api/products');
        products = await res.json();
        renderStats();
        renderProducts();

        // 保留已选中的用户
        const currentUserId = document.getElementById('userId').value;
        const currentProductId = document.getElementById('productId').value;

        renderFormOptions();

        if (currentUserId) document.getElementById('userId').value = currentUserId;
        if (currentProductId) document.getElementById('productId').value = currentProductId;
        updateStockHint();
    } catch (err) {
        console.error(err);
    }
}

// ========== 查询订单 ==========
async function queryOrder(e) {
    e.preventDefault();

    const orderId = document.getElementById('orderId').value;
    if (!orderId) {
        showToast('请输入订单编号', 'error');
        return;
    }

    const btn = e.target.querySelector('.btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span>🔍 查询中...</span>';

    try {
        const res = await fetch(`/api/orders/${orderId}`);
        const result = await res.json();

        const resultArea = document.getElementById('queryResult');

        if (result.code === 200 && result.data) {
            const data = result.data;
            resultArea.style.display = 'block';
            resultArea.innerHTML = `
                <div class="order-detail">
                    <div class="order-header">
                        <span class="order-id">订单编号：<strong>#${data.orderId}</strong></span>
                        <span class="order-status">✅ 有效</span>
                    </div>
                    <div class="order-info-grid">
                        <div class="info-item">
                            <div class="info-label">👤 用户</div>
                            <div class="info-value">${data.userName}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">📦 商品</div>
                            <div class="info-value">${data.productName}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">🔢 数量</div>
                            <div class="info-value">${data.quantity} 件</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">💰 总价</div>
                            <div class="info-value price"><span class="currency">¥</span>${formatPrice(data.totalPrice)}</div>
                        </div>
                        <div class="info-item full">
                            <div class="info-label">🕐 下单时间</div>
                            <div class="info-value">${data.orderTime}</div>
                        </div>
                    </div>
                </div>
            `;
            showToast('订单查询成功', 'success');
        } else {
            resultArea.style.display = 'block';
            resultArea.innerHTML = `<div class="result-error">❌ ${result.message || '订单不存在'}</div>`;
            showToast(result.message || '订单不存在', 'error');
        }
    } catch (err) {
        console.error(err);
        const resultArea = document.getElementById('queryResult');
        resultArea.style.display = 'block';
        resultArea.innerHTML = `<div class="result-error">❌ 查询失败，请检查订单编号是否正确</div>`;
        showToast('查询失败', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ========== 数量 +/- ==========
function adjustQuantity(delta) {
    const input = document.getElementById('quantity');
    let value = Number(input.value) || 1;
    value = Math.max(1, value + delta);
    const product = products.find(p => p.id === Number(document.getElementById('productId').value));
    if (product && value > product.stock) value = product.stock;
    input.value = value;
    updateStockHint();
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function () {
    // 加载数据
    loadData();

    // 创建订单表单
    document.getElementById('createForm').addEventListener('submit', createOrder);

    // 查询订单表单
    document.getElementById('queryForm').addEventListener('submit', queryOrder);

    // 数量加减
    document.getElementById('qtyMinus').addEventListener('click', () => adjustQuantity(-1));
    document.getElementById('qtyPlus').addEventListener('click', () => adjustQuantity(1));

    // 商品切换时更新库存提示
    document.getElementById('productId').addEventListener('change', updateStockHint);
    document.getElementById('quantity').addEventListener('input', updateStockHint);
});
