#!/bin/bash

# EyeOfWeb Production Startup Script
# Bu script production ortamında uygulamayı başlatır

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="EyeOfWeb"
VENV_PATH="$SCRIPT_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOG_DIR/eyeofweb.pid"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create necessary directories
create_directories() {
    log_info "Gerekli dizinler oluşturuluyor..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$SCRIPT_DIR/uploads"
    mkdir -p "$SCRIPT_DIR/temp"
    mkdir -p "$SCRIPT_DIR/certs"
    log_success "Dizinler oluşturuldu"
}

# Check if running as root
check_user() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Bu script root kullanıcısı ile çalıştırılmamalıdır!"
        exit 1
    fi
}

# Check system dependencies
check_dependencies() {
    log_info "Sistem bağımlılıkları kontrol ediliyor..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 bulunamadı! Lütfen Python 3.8+ yükleyin."
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 bulunamadı! Lütfen pip yükleyin."
        exit 1
    fi
    
    log_success "Sistem bağımlılıkları tamam"
}

# Setup virtual environment
setup_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        log_info "Python virtual environment oluşturuluyor..."
        python3 -m venv "$VENV_PATH"
        log_success "Virtual environment oluşturuldu"
    else
        log_info "Virtual environment zaten mevcut"
    fi
    
    # Activate virtual environment
    log_info "Virtual environment aktifleştiriliyor..."
    source "$VENV_PATH/bin/activate"
    
    # Upgrade pip
    log_info "pip güncelleniyor..."
    pip install --upgrade pip
    
    # Install requirements
    log_info "Python bağımlılıkları yükleniyor..."
    pip install -r "$REQUIREMENTS_FILE"
    log_success "Bağımlılıklar yüklendi"
}

# Check if application is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log_warning "Uygulama zaten çalışıyor (PID: $pid)"
            echo "Durdurmak için: kill $pid"
            exit 1
        else
            log_info "Eski PID dosyası temizleniyor..."
            rm -f "$PID_FILE"
        fi
    fi
}

# Check GPU and CUDA
check_gpu() {
    log_info "GPU ve CUDA desteği kontrol ediliyor..."
    
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits
        log_success "NVIDIA GPU bulundu"
        export USE_CUDA=true
    else
        log_warning "NVIDIA GPU bulunamadı, CPU kullanılacak"
        export USE_CUDA=false
    fi
}

# Set environment variables
set_environment() {
    log_info "Ortam değişkenleri ayarlanıyor..."
    
    export FLASK_ENV=production
    export FLASK_HOST=${FLASK_HOST:-"0.0.0.0"}
    export FLASK_PORT=${FLASK_PORT:-5000}
    export GUNICORN_WORKERS=${GUNICORN_WORKERS:-8}
    export GUNICORN_THREADS=${GUNICORN_THREADS:-4}
    export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
    
    log_success "Ortam değişkenleri ayarlandı"
}

# Monitor function
monitor_app() {
    local max_attempts=60
    local attempt=1
    
    log_info "Uygulama başlatma bekleniyor..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "http://localhost:${FLASK_PORT}/health" > /dev/null 2>&1; then
            log_success "Uygulama başarıyla başlatıldı!"
            log_info "URL: http://localhost:${FLASK_PORT}"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    log_error "Uygulama başlatılamadı! Logları kontrol edin."
    return 1
}

# Start application
start_app() {
    log_info "$APP_NAME production modunda başlatılıyor..."
    
    # Activate virtual environment
    source "$VENV_PATH/bin/activate"
    
    # Start the application
    nohup python run.py \
        --mode production \
        --workers $GUNICORN_WORKERS \
        --threads $GUNICORN_THREADS \
        --timeout 120 \
        > "$LOG_DIR/app.log" 2>&1 &
    
    local app_pid=$!
    echo $app_pid > "$PID_FILE"
    
    log_success "Uygulama başlatıldı (PID: $app_pid)"
    log_info "Loglar: $LOG_DIR/app.log"
    
    # Monitor startup
    monitor_app
}

# Stop application
stop_app() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        log_info "Uygulama durduruluyor (PID: $pid)..."
        
        if ps -p $pid > /dev/null 2>&1; then
            kill -TERM $pid
            sleep 5
            
            if ps -p $pid > /dev/null 2>&1; then
                log_warning "Normal durdurma başarısız, zorla durdurma..."
                kill -KILL $pid
            fi
        fi
        
        rm -f "$PID_FILE"
        log_success "Uygulama durduruldu"
    else
        log_warning "PID dosyası bulunamadı, uygulama çalışmıyor olabilir"
    fi
}

# Restart application
restart_app() {
    log_info "Uygulama yeniden başlatılıyor..."
    stop_app
    sleep 2
    start_app
}

# Show status
show_status() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log_success "Uygulama çalışıyor (PID: $pid)"
            
            # Show resource usage
            ps -p $pid -o pid,ppid,user,%cpu,%mem,vsz,rss,tty,stat,start,time,command
            
            # Show network connections
            echo -e "\nAktif bağlantılar:"
            netstat -tlnp 2>/dev/null | grep $pid || echo "Bağlantı bilgisi alınamadı"
            
        else
            log_error "PID dosyası mevcut ama süreç çalışmıyor"
            rm -f "$PID_FILE"
        fi
    else
        log_warning "Uygulama çalışmıyor"
    fi
}

# Main function
main() {
    clear
    echo "========================================"
    echo "  $APP_NAME Production Manager"
    echo "========================================"
    
    case "${1:-start}" in
        start)
            check_user
            create_directories
            check_dependencies
            setup_venv
            check_running
            check_gpu
            set_environment
            start_app
            ;;
        stop)
            stop_app
            ;;
        restart)
            restart_app
            ;;
        status)
            show_status
            ;;
        setup)
            check_user
            create_directories
            check_dependencies
            setup_venv
            check_gpu
            log_success "Kurulum tamamlandı! 'bash start_production.sh start' ile başlatabilirsiniz."
            ;;
        *)
            echo "Kullanım: $0 {start|stop|restart|status|setup}"
            echo ""
            echo "Komutlar:"
            echo "  start   - Uygulamayı başlat"
            echo "  stop    - Uygulamayı durdur"
            echo "  restart - Uygulamayı yeniden başlat"
            echo "  status  - Durum bilgisi göster"
            echo "  setup   - İlk kurulum yap"
            exit 1
            ;;
    esac
}

# Script'i çalıştır
main "$@" 