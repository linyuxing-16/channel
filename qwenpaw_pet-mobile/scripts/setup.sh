#!/usr/bin/env bash
# Qwenpaw Pet Mobile - 外部资源下载脚本
# 使用: bash scripts/setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PUBLIC_DIR="$PROJECT_DIR/public"
LIB_DIR="$PROJECT_DIR/src/lib"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# ── 1. Live2D Cubism Core SDK ──
download_live2d_core() {
  echo ""
  echo "=== Live2D Cubism Core SDK ==="
  if [ -f "$LIB_DIR/live2dcubismcore.min.js" ]; then
    info "Live2D Core 已存在，跳过"
    return
  fi

  warn "Live2D Cubism Core 需要手动从 Live2D 官网下载。"
  warn "请访问: https://www.live2d.com/download/cubism-sdk/download-web/"
  warn "下载 Cubism 5 SDK for Web，解压后找到 live2dcubismcore.min.js"
  warn "放到: $LIB_DIR/live2dcubismcore.min.js"
  echo ""
  read -rp "已下载并放置好文件？(y/N) " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    warn "跳过 Live2D Core，将使用备用图片模式运行"
    return
  fi
  if [ -f "$LIB_DIR/live2dcubismcore.min.js" ]; then
    info "Live2D Core 就绪"
  else
    error "文件未找到，请手动放置"
  fi
}

# ── 2. Live2D Hiyori 测试模型 ──
download_hiyori_model() {
  echo ""
  echo "=== Live2D Hiyori 测试模型 ==="
  local model_dir="$PUBLIC_DIR/live2d-models/hiyori"
  if [ -f "$model_dir/model.model3.json" ]; then
    info "Hiyori 模型已存在，跳过"
    return
  fi

  warn "Hiyori 测试模型需要从 Live2D 官网下载:"
  warn "https://www.live2d.com/download/sample-data/"
  warn "下载后放入: $model_dir/"
  echo ""
  read -rp "已下载并放置好文件？(y/N) " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    warn "跳过 Hiyori 模型，将使用备用图片模式运行"
    return
  fi
  if [ -f "$model_dir/model.model3.json" ]; then
    info "Hiyori 模型就绪"
  else
    error "文件未找到，请手动放置"
  fi
}

# ── 3. sherpa-onnx KWS WASM ──
download_kws_wasm() {
  echo ""
  echo "=== sherpa-onnx KWS WASM ==="
  local kws_wasm_dir="$PUBLIC_DIR/sherpa-onnx-wasm/kws"
  if [ -f "$kws_wasm_dir/sherpa-onnx-kws.js" ]; then
    info "KWS WASM 已存在，跳过"
    return
  fi

  mkdir -p "$kws_wasm_dir"
  echo "下载 KWS WASM 源文件..."

  # 从 GitHub 源码仓库下载 KWS WASM 文件
  local files=(
    "wasm/kws/sherpa-onnx-kws.js"
    "wasm/kws/app.js"
    "wasm/kws/index.html"
    "wasm/kws/CMakeLists.txt"
  )

  for f in "${files[@]}"; do
    local url="https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/$f"
    local dest="$kws_wasm_dir/$(basename "$f")"
    echo "  下载: $url"
    curl -sL "$url" -o "$dest"
  done

  warn "KWS WASM 运行时文件 (.wasm + .data) 需要从源码构建。"
  warn "构建指南: https://github.com/k2-fsa/sherpa-onnx/tree/master/wasm"
  warn "或使用 Web Speech API 替代方案（已内置）。"
  echo ""
}

# ── 4. VAD WASM（已预置） ──
check_vad_wasm() {
  echo ""
  echo "=== sherpa-onnx VAD WASM ==="
  local vad_dir="$PUBLIC_DIR/sherpa-onnx-wasm/vad"
  if [ -f "$vad_dir/sherpa-onnx-vad.js" ]; then
    info "VAD WASM 已就绪 ✓"
    return
  fi
  warn "VAD WASM 未找到，语音静音检测将不可用"
}

# ── 5. KWS 模型文件（已预置） ──
check_kws_models() {
  echo ""
  echo "=== KWS 模型文件 ==="
  local model_dir="$PUBLIC_DIR/sherpa-onnx-wasm/kws-models"
  if [ -f "$model_dir/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01-mobile/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx" ]; then
    info "KWS 模型文件已就绪 ✓"
    return
  fi
  warn "KWS 模型文件未找到"
}

# ── 6. 宠物备用图片 ──
create_placeholder_images() {
  echo ""
  echo "=== 备用宠物图片 ==="
  local img_dir="$PROJECT_DIR/src/assets/images"
  mkdir -p "$img_dir"

  # 创建简单的 SVG 占位图（当没有 Live2D 且没有宠物图片时使用）
  if [ ! -f "$img_dir/silent.svg" ]; then
    cat > "$img_dir/silent.svg" << 'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <circle cx="100" cy="100" r="80" fill="#a8d8ea" opacity="0.8"/>
  <circle cx="70" cy="85" r="10" fill="#333"/>
  <circle cx="130" cy="85" r="10" fill="#333"/>
  <path d="M 70 120 Q 100 145 130 120" stroke="#333" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>
SVG
    info "创建 silent.svg 占位图"
  fi

  if [ ! -f "$img_dir/thinking.svg" ]; then
    cat > "$img_dir/thinking.svg" << 'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <circle cx="100" cy="100" r="80" fill="#7ec8e3" opacity="0.8"/>
  <circle cx="70" cy="85" r="10" fill="#555"/>
  <circle cx="130" cy="85" r="10" fill="#555"/>
  <ellipse cx="100" cy="120" rx="30" ry="15" fill="#555" opacity="0.3"/>
  <line x1="140" y1="50" x2="165" y2="30" stroke="#ffd700" stroke-width="3" stroke-linecap="round"/>
  <circle cx="165" cy="25" r="8" fill="#ffd700" opacity="0.8"/>
</svg>
SVG
    info "创建 thinking.svg 占位图"
  fi

  if [ ! -f "$img_dir/speaking.svg" ]; then
    cat > "$img_dir/speaking.svg" << 'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <circle cx="100" cy="100" r="80" fill="#64b5f6" opacity="0.8"/>
  <circle cx="70" cy="85" r="10" fill="#333"/>
  <circle cx="130" cy="85" r="10" fill="#333"/>
  <path d="M 70 115 Q 100 145 130 115" stroke="#333" stroke-width="3" fill="#ff6b6b" fill-opacity="0.3" stroke-linecap="round"/>
  <path d="M 60 115 Q 100 150 140 115" stroke="#333" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.3"/>
</svg>
SVG
    info "创建 speaking.svg 占位图"
  fi
}

# ── 主流程 ──
main() {
  echo "========================================"
  echo "  Qwenpaw Pet Mobile - 资源下载脚本"
  echo "========================================"
  echo ""

  download_live2d_core
  download_hiyori_model
  download_kws_wasm
  check_vad_wasm
  check_kws_models
  create_placeholder_images

  echo ""
  echo "========================================"
  echo "  设置完成！"
  echo ""
  echo "  下一步:"
  echo "    npm run dev    # 启动开发服务器"
  echo "    npm run build  # 构建生产版本"
  echo "========================================"
}

main
