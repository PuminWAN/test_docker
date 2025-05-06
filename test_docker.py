import datetime
import time

def main():
    print("🚀 Container Started: test_docker.py is running")
    print("⏰ Current Time in Asia/Bangkok:")

    while True:
        now = datetime.datetime.now()
        print(f"🕒 {now.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(5) 

if __name__ == "__main__":
    main()
