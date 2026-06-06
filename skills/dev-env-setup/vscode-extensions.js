// ============================================================
// VS Code 推荐扩展列表
// 使用方式: VS Code 扩展面板搜索安装，或用命令行:
// code --install-extension <extension-id>
// ============================================================

const recommendedExtensions = [
  // ====== 核心必备 ======
  { id: "Vue.volar", name: "Vue Language Features (Volar)", desc: "Vue3 官方语言支持" },
  { id: "dbaeumer.vscode-eslint", name: "ESLint", desc: "JavaScript/TypeScript 代码检查" },
  { id: "esbenp.prettier-vscode", name: "Prettier", desc: "代码格式化" },
  { id: "bradlc.vscode-tailwindcss", name: "Tailwind CSS IntelliSense", desc: "Tailwind CSS 自动补全" },
  { id: "formulahendry.auto-rename-tag", name: "Auto Rename Tag", desc: "HTML标签自动重命名配对" },

  // ====== TypeScript ======
  { id: "ms-vscode.vscode-typescript-next", name: "TypeScript Importer", desc: "自动导入TS模块" },

  // ====== Vue 生态 ======
  { id: "Vue.vscode-typescript-vue-plugin", name: "TypeScript Vue Plugin (Volar)", desc: "Vue TS支持增强" },

  // ====== 小程序/uni-app ======
  { id: "uni-helper.uni-app-vscode", name: "uni-app VSCode Extension", desc: "uni-app 开发支持" },
  { id: "uni-helper.uni-helper-vscode", name: "uni-helper", desc: "uni-app 辅助工具" },

  // ====== Git ======
  { id: "eamodio.gitlens", name: "GitLens", desc: "Git 超级增强" },
  { id: "mhutchie.git-graph", name: "Git Graph", desc: "Git 图形化视图" },

  // ====== 数据库 ======
  { id: "mtxr.sqltools", name: "SQLTools", desc: "数据库管理工具" },

  // ====== API ======
  { id: "humao.rest-client", name: "REST Client", desc: "在编辑器中直接发HTTP请求" },

  // ====== UI美化 ======
  { id: "PKief.material-icon-theme", name: "Material Icon Theme", desc: "文件图标主题" },
  { id: "zhuangtongfa.material-theme", name: "One Dark Pro", desc: "暗色主题" },

  // ====== 效率工具 ======
  { id: "streetsidesoftware.code-spell-checker", name: "Code Spell Checker", desc: "拼写检查" },
  { id: "christian-kohler.path-intellisense", name: "Path Intellisense", desc: "路径自动补全" },
  { id: "usernamehw.errorlens", name: "Error Lens", desc: "行内错误显示" },
  { id: "Gruntfuggly.todo-tree", name: "Todo Tree", desc: "TODO/FIXME 注释树" },
  { id: "wayou.vscode-todo-highlight", name: "Todo Highlight", desc: "TODO 高亮" },

  // ====== 远程开发 ======
  { id: "ms-vscode-remote.remote-ssh", name: "Remote - SSH", desc: "SSH远程开发" },

  // ====== Docker ======
  { id: "ms-azuretools.vscode-docker", name: "Docker", desc: "Docker 支持" }
];

console.log("推荐扩展列表 (" + recommendedExtensions.length + "个):");
console.log("");
recommendedExtensions.forEach((ext, i) => {
  console.log((i+1) + ". " + ext.name + " (" + ext.id + ")");
  console.log("   " + ext.desc);
});
console.log("");
console.log("一键安装命令:");
recommendedExtensions.forEach(ext => {
  console.log("code --install-extension " + ext.id);
});
