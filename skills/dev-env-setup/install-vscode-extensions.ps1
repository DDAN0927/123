# ============================================================
# 一键安装所有 VS Code 推荐扩展
# 用法: 在 PowerShell 中运行此脚本
# ============================================================

$extensions = @(
  # 核心必备
  "Vue.volar",
  "dbaeumer.vscode-eslint",
  "esbenp.prettier-vscode",
  "bradlc.vscode-tailwindcss",
  "formulahendry.auto-rename-tag",
  # TypeScript
  "ms-vscode.vscode-typescript-next",
  # Vue生态
  "Vue.vscode-typescript-vue-plugin",
  # 小程序/uni-app
  "uni-helper.uni-app-vscode",
  "uni-helper.uni-helper-vscode",
  # Git
  "eamodio.gitlens",
  "mhutchie.git-graph",
  # API
  "humao.rest-client",
  # UI美化
  "PKief.material-icon-theme",
  "zhuangtongfa.material-theme",
  # 效率工具
  "streetsidesoftware.code-spell-checker",
  "christian-kohler.path-intellisense",
  "usernamehw.errorlens",
  "Gruntfuggly.todo-tree",
  # Docker
  "ms-azuretools.vscode-docker"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装 VS Code 推荐扩展 ($($extensions.Count)个)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$installed = 0
$failed = 0
foreach ($ext in $extensions) {
  Write-Host -NoNewline "  [$installed/$($extensions.Count)] $ext ... "
  try {
    code --install-extension $ext --force 2>&1 | Out-Null
    $installed++
    Write-Host "OK" -ForegroundColor Green
  } catch {
    $failed++
    Write-Host "FAIL" -ForegroundColor Red
  }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  完成! 安装: $installed, 失败: $failed" -ForegroundColor $(if($failed -eq 0){"Green"}else{"Yellow"})
Write-Host "========================================" -ForegroundColor Cyan
