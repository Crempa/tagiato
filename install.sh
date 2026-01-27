#!/bin/bash
#
# Tagiato Installation Script
# Handles installation, development setup, and uninstallation
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="tagiato"
MIN_PYTHON_VERSION="3.10"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if running on macOS
check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        print_error "This script is designed for macOS only"
        exit 1
    fi
}

# Detect user's shell
detect_shell() {
    local shell_name
    shell_name=$(basename "$SHELL")

    case "$shell_name" in
        bash)
            SHELL_RC="$HOME/.bashrc"
            if [[ -f "$HOME/.bash_profile" ]]; then
                SHELL_RC="$HOME/.bash_profile"
            fi
            ;;
        zsh)
            SHELL_RC="$HOME/.zshrc"
            ;;
        fish)
            SHELL_RC="$HOME/.config/fish/config.fish"
            ;;
        *)
            SHELL_RC="$HOME/.profile"
            ;;
    esac
}

# Find suitable Python installation
find_python() {
    local python_cmd=""

    # Try specific versions first (newest to oldest)
    for version in python3.13 python3.12 python3.11 python3.10; do
        if command -v "$version" &> /dev/null; then
            local ver
            ver=$("$version" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [[ -n "$ver" ]]; then
                python_cmd="$version"
                break
            fi
        fi
    done

    # Fallback to python3
    if [[ -z "$python_cmd" ]] && command -v python3 &> /dev/null; then
        local ver
        ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        local major minor
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]; then
            python_cmd="python3"
        fi
    fi

    if [[ -z "$python_cmd" ]]; then
        return 1
    fi

    PYTHON_CMD="$python_cmd"
    PYTHON_VERSION=$("$python_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    return 0
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    local all_ok=true

    # Check Homebrew
    if command -v brew &> /dev/null; then
        print_success "Homebrew is installed"
    else
        print_error "Homebrew is not installed"
        print_info "Install from: https://brew.sh"
        all_ok=false
    fi

    # Check Python
    if find_python; then
        print_success "Python $PYTHON_VERSION found ($PYTHON_CMD)"
    else
        print_error "Python $MIN_PYTHON_VERSION+ is required"
        print_info "Install with: brew install python@3.12"
        all_ok=false
    fi

    # Check pipx
    if command -v pipx &> /dev/null; then
        print_success "pipx is installed"
    else
        print_error "pipx is not installed"
        print_info "Install with: brew install pipx && pipx ensurepath"
        all_ok=false
    fi

    # Check Claude CLI (required for tagiato)
    if command -v claude &> /dev/null; then
        print_success "Claude CLI is installed"
    else
        print_warning "Claude CLI is not installed"
        print_info "Install with: npm install -g @anthropic-ai/claude-cli"
        print_info "Tagiato requires Claude CLI for AI descriptions"
    fi

    echo ""
    if $all_ok; then
        print_success "All prerequisites satisfied!"
        return 0
    else
        print_error "Some prerequisites are missing"
        return 1
    fi
}

# Install via pipx (production)
install_production() {
    print_header "Installing Tagiato (Production)"

    if ! check_prerequisites; then
        exit 1
    fi

    cd "$SCRIPT_DIR"

    # Check if already installed
    if pipx list 2>/dev/null | grep -q "^\\s*package $APP_NAME"; then
        print_info "Tagiato is already installed, updating..."
        pipx upgrade "$APP_NAME" --include-injected || pipx install . --force
    else
        print_info "Installing tagiato via pipx..."
        pipx install .
    fi

    echo ""
    print_success "Installation complete!"
    echo ""
    print_info "Run 'tagiato --help' to get started"
}

# Update existing installation
update_installation() {
    print_header "Updating Tagiato"

    cd "$SCRIPT_DIR"

    if pipx list 2>/dev/null | grep -q "^\\s*package $APP_NAME"; then
        print_info "Reinstalling from source..."
        pipx install . --force
        print_success "Update complete!"
    else
        print_error "Tagiato is not installed"
        print_info "Run './install.sh' to install"
        exit 1
    fi
}

# Setup development environment
setup_development() {
    print_header "Setting Up Development Environment"

    if ! find_python; then
        print_error "Python $MIN_PYTHON_VERSION+ is required"
        exit 1
    fi

    cd "$SCRIPT_DIR"

    # Create virtual environment
    if [[ -d ".venv" ]]; then
        print_warning "Virtual environment already exists"
        read -p "Recreate it? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf .venv
        else
            print_info "Keeping existing environment"
        fi
    fi

    if [[ ! -d ".venv" ]]; then
        print_info "Creating virtual environment with $PYTHON_CMD..."
        "$PYTHON_CMD" -m venv .venv
    fi

    # Activate and install
    print_info "Installing package in editable mode with test dependencies..."
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e ".[test]"

    echo ""
    print_success "Development environment ready!"
    echo ""
    print_info "Activate with: source .venv/bin/activate"
    print_info "Run tests with: make test"
    print_info "Run app with: tagiato --help"
}

# Uninstall completely
uninstall() {
    print_header "Uninstalling Tagiato"

    # Remove pipx installation
    if pipx list 2>/dev/null | grep -q "^\\s*package $APP_NAME"; then
        print_info "Removing pipx installation..."
        pipx uninstall "$APP_NAME"
        print_success "Removed pipx installation"
    else
        print_info "No pipx installation found"
    fi

    # Remove development environment
    if [[ -d "$SCRIPT_DIR/.venv" ]]; then
        print_info "Removing development environment..."
        rm -rf "$SCRIPT_DIR/.venv"
        print_success "Removed .venv"
    fi

    # Clean build artifacts
    print_info "Cleaning build artifacts..."
    rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist" "$SCRIPT_DIR"/*.egg-info
    find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

    echo ""
    print_success "Uninstallation complete!"
}

# Show usage
usage() {
    echo "Tagiato Installation Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  (none)      Install tagiato via pipx (production)"
    echo "  --dev       Set up development environment"
    echo "  --update    Update existing installation"
    echo "  --check     Check prerequisites only"
    echo "  --uninstall Remove tagiato completely"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Install for regular use"
    echo "  $0 --dev        # Set up for development"
    echo "  $0 --update     # Update after code changes"
}

# Main
main() {
    check_macos
    detect_shell

    case "${1:-}" in
        --dev)
            setup_development
            ;;
        --update)
            update_installation
            ;;
        --check)
            check_prerequisites
            ;;
        --uninstall)
            uninstall
            ;;
        --help|-h)
            usage
            ;;
        "")
            install_production
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"
