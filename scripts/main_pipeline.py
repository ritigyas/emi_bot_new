import subprocess, os, sys, time, logging

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/pipeline.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def run_step(name, command):
    logging.info(f"=== Starting: {name} ===")
    print(f"\n▶ {name} ...")
    try:
        subprocess.run(command, check=True)
        logging.info(f"✅ Completed: {name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed: {name} | Error: {e}")
        print(f"❌ Step failed: {name}. Check logs/pipeline.log")
        sys.exit(1)  # stop the pipeline on failure

if __name__ == "__main__":
    start = time.time()

    # Step 1: Prepare Customer CSV
    run_step("Data Preparation", ["python", "scripts/prepare_customer_csv.py"])

    # Step 2: Generate Base Videos (only if not already present)
    if not os.path.exists("assets/base_videos/base_hindi.mp4"):
        run_step("Generate Base Heygen Videos", ["python", "scripts/generate_base_videos.py"])
    else:
        print("✅ Base videos already exist, skipping...")

    # Step 3: Generate Audio Snippets
    run_step("Generate Personalized Audio Snippets", ["python", "scripts/generate_audio_snippets.py"])

    # Step 4: Generate Visual Cards
    run_step("Generate Visual Cards", ["python", "scripts/generate_cards.py"])

    # Step 5: Compose Final Videos
    run_step("Compose Personalized Videos", ["python", "scripts/compose_videos.py"])

    elapsed = round((time.time() - start) / 60, 2)
    logging.info(f"🏁 Pipeline completed successfully in {elapsed} minutes.")
    print(f"\n🏁 All done! Total time: {elapsed} min")
