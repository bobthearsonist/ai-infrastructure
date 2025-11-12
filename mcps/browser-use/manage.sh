#!/bin/bash

# Browser-Use MCP Setup and Management Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
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

# Check if .env file exists
check_env_file() {
    if [ ! -f ".env" ]; then
        log_warning ".env file not found. Creating from template..."
        cp .env.example .env
        log_info "Please edit .env file with your API keys:"
        log_info "  OPENAI_API_KEY=your_key_here"
        log_info "  ANTHROPIC_API_KEY=your_key_here"
        return 1
    fi
    return 0
}

# Build the container
build_container() {
    log_info "Building browser-use MCP container..."
    docker-compose build
    log_success "Container built successfully"
}

# Start the services
start_services() {
    log_info "Starting browser-use MCP services..."
    docker-compose up -d

    # Wait for health check
    log_info "Waiting for services to be healthy..."
    sleep 10

    if docker-compose ps | grep -q "Up (healthy)"; then
        log_success "Services started successfully"
        return 0
    else
        log_warning "Services started but health check pending..."
        return 1
    fi
}

# Stop the services
stop_services() {
    log_info "Stopping browser-use MCP services..."
    docker-compose down
    log_success "Services stopped"
}

# Check service status
check_status() {
    echo -e "\n${BLUE}=== Browser-Use MCP Status ===${NC}"
    docker-compose ps

    echo -e "\n${BLUE}=== Health Check ===${NC}"
    if curl -s http://localhost:7009/health > /dev/null; then
        log_success "Health check passed"
        curl -s http://localhost:7009/health
    else
        log_error "Health check failed"
    fi

    echo -e "\n${BLUE}=== MCP Endpoint ===${NC}"
    if curl -s http://localhost:7009/mcp > /dev/null; then
        log_success "MCP endpoint accessible"
    else
        log_error "MCP endpoint not accessible"
    fi

    echo -e "\n${BLUE}=== Recent Logs ===${NC}"
    docker-compose logs --tail=10 browser-use-mcp
}

# Test MCP connectivity
test_mcp() {
    log_info "Testing MCP server connectivity..."

    echo -e "\n${BLUE}=== Health Check ===${NC}"
    if curl -s http://localhost:7009/health; then
        log_success "Health endpoint responding"
    else
        log_error "Health endpoint not responding"
        return 1
    fi

    echo -e "\n${BLUE}=== MCP Endpoint ===${NC}"
    if curl -s http://localhost:7009/mcp; then
        log_success "MCP endpoint responding"
    else
        log_error "MCP endpoint not responding"
        return 1
    fi
}

# Show logs
show_logs() {
    local lines="${1:-50}"
    docker-compose logs --tail="$lines" -f browser-use-mcp
}

# Update container
update_container() {
    log_info "Updating browser-use MCP container..."
    docker-compose pull
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    log_success "Container updated"
}

# Interactive setup
interactive_setup() {
    echo -e "\n${BLUE}=== Browser-Use MCP Interactive Setup ===${NC}\n"

    # Check environment
    if ! check_env_file; then
        echo -e "\n${YELLOW}Please edit the .env file and run this script again.${NC}"
        return 1
    fi

    # Ask about building
    read -p "Build the container? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_container
    fi

    # Ask about starting
    read -p "Start the services? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_services
    fi

    echo -e "\n${GREEN}Setup complete!${NC}"
    echo -e "\nNext steps:"
    echo -e "1. Test connectivity: $0 test-mcp"
    echo -e "2. Check status: $0 status"
    echo -e "3. View logs: $0 logs"
    echo -e "4. Connect your MCP client to: http://localhost:7009/mcp"
}

# Main command handler
case "${1:-help}" in
    "setup" | "install")
        interactive_setup
        ;;
    "build")
        check_env_file && build_container
        ;;
    "start" | "up")
        check_env_file && start_services
        ;;
    "stop" | "down")
        stop_services
        ;;
    "restart")
        stop_services && sleep 2 && start_services
        ;;
    "status")
        check_status
        ;;
    "logs")
        show_logs "${2:-50}"
        ;;
    "test-mcp")
        test_mcp
        ;;
    "update")
        update_container
        ;;
    "help" | *)
        echo -e "\n${BLUE}Browser-Use MCP Management Script${NC}\n"
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  setup              Interactive setup process"
        echo "  build              Build the Docker container"
        echo "  start              Start the MCP server"
        echo "  stop               Stop the MCP server"
        echo "  restart            Restart the MCP server"
        echo "  status             Show server status and health"
        echo "  logs [lines]       Show container logs (default: 50 lines)"
        echo "  test-mcp           Test MCP server connectivity"
        echo "  update             Update and rebuild container"
        echo "  help               Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 setup"
        echo "  $0 start"
        echo "  $0 test-mcp"
        echo "  $0 status"
        echo "  $0 logs 100"
        echo ""
        echo "MCP Endpoints:"
        echo "  Health:  http://localhost:7009/health"
        echo "  MCP:     http://localhost:7009/mcp"
        echo ""
        ;;
esac
