/**
 * Tailwind 构建配置。
 * 改了 index.html 里用到的类名后必须重新编译 lib/tailwind.css，否则新类不会生效。
 *
 *   cd tools/tailwind && npm i && npm run build
 *
 * content 用 __dirname 绝对化，避免「在哪个目录执行」影响扫描结果（踩过：从仓库根跑，
 * 相对路径解析错，产物只有 4.7KB，页面样式全丢）。
 */
const path = require("path");

module.exports = {
  content: [path.resolve(__dirname, "../../index.html")],
  theme: { extend: {} },
  plugins: [],
};
