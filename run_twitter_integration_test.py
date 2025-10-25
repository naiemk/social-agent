#!/usr/bin/env python3
"""
Twitter Client Integration Test Runner

This script demonstrates how to run the real Twitter API integration test.
It will actually search for tweets, like them, and reply to them using your Twitter account.

Usage:
1. Set your Twitter API credentials:
   export TWITTER_BEARER_TOKEN="your_bearer_token_here"
   export TWITTER_USER_ID="your_user_id_here"

2. Run the test:
   python run_twitter_integration_test.py

The test will:
- Search for tweets about "AI machine learning"
- Like the first tweet found
- Reply to that tweet
- Verify all operations worked correctly
"""

import os
import sys
import subprocess

def main():
    print("🐦 Twitter Client Integration Test Runner")
    print("=" * 50)
    
    # Check for credentials
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    user_id = os.getenv('TWITTER_USER_ID')
    
    if not bearer_token or not user_id:
        print("❌ Missing Twitter API credentials!")
        print("\nTo run the integration test, you need to set these environment variables:")
        print("   export TWITTER_BEARER_TOKEN='your_bearer_token'")
        print("   export TWITTER_USER_ID='your_user_id'")
        print("\nYou can get these from:")
        print("   https://developer.twitter.com/en/portal/dashboard")
        print("\n⚠️  WARNING: This test will make REAL API calls and:")
        print("   - Search for tweets about 'AI machine learning'")
        print("   - LIKE a tweet (this will be visible on your account)")
        print("   - REPLY to a tweet (this will be visible on your account)")
        print("\nMake sure you're okay with this before proceeding!")
        return 1
    
    print("✅ Found Twitter credentials")
    print(f"   User ID: {user_id}")
    print(f"   Bearer Token: {bearer_token[:10]}...")
    
    print("\n🚀 Starting REAL Twitter API Integration Test...")
    print("This will make actual API calls to Twitter!")
    print("\nPress Ctrl+C to cancel, or wait 5 seconds to continue...")
    
    try:
        import time
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        return 1
    
    # Run the integration test
    try:
        print("\n" + "=" * 50)
        print("Running integration test...")
        print("=" * 50)
        
        # Run the test using pytest
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'sources/test/test_tweetpy_client.py::test_real_integration',
            '-v', '-s'
        ], cwd='/workspaces/social-agent')
        
        if result.returncode == 0:
            print("\n🎉 Integration test PASSED!")
            print("Your Twitter client is working perfectly!")
            print("\n✅ Verified functionality:")
            print("   - Tweet search")
            print("   - Tweet liking")
            print("   - Tweet replying")
            print("   - User info retrieval")
            print("   - Tweet details retrieval")
        else:
            print("\n❌ Integration test FAILED!")
            print("Check the output above for details.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
