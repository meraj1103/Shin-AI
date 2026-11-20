import time
from Shin.core import island_bridge

def main():
    print("=" * 60)
    print("🚀 LIVE SHIN <-> DYNAMIC ISLAND CONNECTION TEST")
    print("=" * 60)
    print("\n[Step 1] Triggering Visual Thinking...")
    print("Look at your Dynamic Island at the top of your screen!")
    island_bridge.show_thinking()
    time.sleep(2.5)

    print("\n[Step 2] Sending Shin's Voice Response...")
    island_bridge.show_speaking("Hey MJ! Your Dynamic Island is now officially connected to Shin! 🚀")
    time.sleep(3.5)

    print("\n[Step 3] Resetting to Idle...")
    island_bridge.show_idle()
    print("\n✅ Test complete! Check your Dynamic Island at the top of your screen.")

if __name__ == "__main__":
    main()
