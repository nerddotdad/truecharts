#!/bin/bash
# Element Registration Token Manager
# This script helps you create and manage registration tokens for your private Matrix server

echo "🏠 Hoth Private Matrix - Registration Token Manager"
echo "=================================================="
echo ""

# Function to create a single-use token
create_single_token() {
    echo "Creating single-use registration token..."
    token=$(kubectl exec -n communication deployment/element-server-suite-matrix-authentication-service -- mas-cli manage issue-user-registration-token 2>&1 | grep -o 'Created user registration token: [A-Za-z0-9]*' | sed 's/Created user registration token: //')
}

# Function to create a multi-use token
create_multi_token() {
    echo "How many times should this token be usable? (default: 5)"
    read -r usage_limit
    usage_limit=${usage_limit:-5}
    
    echo "Creating token usable $usage_limit times..."
    token=$(kubectl exec -n communication deployment/element-server-suite-matrix-authentication-service -- mas-cli manage issue-user-registration-token --usage-limit "$usage_limit" 2>&1 | grep -o 'Created user registration token: [A-Za-z0-9]*' | sed 's/Created user registration token: //')
}

# Function to create an unlimited token
create_unlimited_token() {
    echo "Creating unlimited-use registration token..."
    token=$(kubectl exec -n communication deployment/element-server-suite-matrix-authentication-service -- mas-cli manage issue-user-registration-token --unlimited 2>&1 | grep -o 'Created user registration token: [A-Za-z0-9]*' | sed 's/Created user registration token: //')
}

# Function to create a token with expiration
create_expiring_token() {
    echo "How many days should this token be valid? (default: 7)"
    read -r days
    days=${days:-7}
    seconds=$((days * 24 * 60 * 60))
    
    echo "Creating token valid for $days days..."
    token=$(kubectl exec -n communication deployment/element-server-suite-matrix-authentication-service -- mas-cli manage issue-user-registration-token --expires-in "$seconds" 2>&1 | grep -o 'Created user registration token: [A-Za-z0-9]*' | sed 's/Created user registration token: //')
}

# Main menu
echo "Choose an option:"
echo "1) Create single-use token (recommended for individual invites)"
echo "2) Create multi-use token (for family groups)"
echo "3) Create unlimited token (for ongoing invites)"
echo "4) Create expiring token (for time-limited invites)"
echo "5) Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        create_single_token
        ;;
    2)
        create_multi_token
        ;;
    3)
        create_unlimited_token
        ;;
    4)
        create_expiring_token
        ;;
    5)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "✅ Token created successfully!"
echo ""
echo "📋 Instructions for your friends/family:"
echo "1. Go to https://element.hoth.systems"
echo "2. Click 'Sign In'"
echo "3. Click 'Create account'"
echo "4. Enter the registration token when prompted:"
echo ""
echo "🔑 REGISTRATION TOKEN:"
echo "======================"
echo "$token"
echo "======================"
echo ""
echo "5. Complete account setup"
echo ""
echo "🔒 This ensures only people you invite can join your private server!"
echo ""
echo "💡 You can copy the token above and send it to your friend/family member!"
