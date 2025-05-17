import os
import duckdb
from pathlib import Path
import argparse
from tensorboard.backend.event_processing import event_accumulator
import base64

# Set paths
RUNS_DIR = Path(__file__).parent.parent / 'pgc' / 'runs'
DUCKDB_FILE = Path(__file__).parent / 'brain_stats.duckdb'

# Connect to DuckDB and create tables
con = duckdb.connect(str(DUCKDB_FILE))
con.execute('''
CREATE TABLE IF NOT EXISTS scalars (
    study TEXT,
    tag TEXT,
    step INTEGER,
    wall_time DOUBLE,
    value DOUBLE
)
''')
con.execute('''
CREATE TABLE IF NOT EXISTS images (
    study TEXT,
    tag TEXT,
    step INTEGER,
    wall_time DOUBLE,
    image_format TEXT,
    image_data BLOB
)
''')

def setup_database(mode='append'):
    """Set up the database based on the specified mode"""
    con = duckdb.connect(DUCKDB_FILE)
    
    if mode == 'reset':
        # Drop tables if they exist
        con.execute("DROP TABLE IF EXISTS scalars")
        con.execute("DROP TABLE IF EXISTS images")
        print(f"Reset: Dropped existing tables in {DUCKDB_FILE}")
    
    # Create tables if they don't exist
    con.execute("""
    CREATE TABLE IF NOT EXISTS scalars (
        study VARCHAR,
        tag VARCHAR,
        step BIGINT,
        wall_time DOUBLE,
        value DOUBLE
    )
    """)
    
    con.execute("""
    CREATE TABLE IF NOT EXISTS images (
        study VARCHAR,
        tag VARCHAR,
        step BIGINT,
        wall_time DOUBLE,
        image_format VARCHAR,
        image_data BLOB
    )
    """)
    
    con.close()

def process_event_file(event_file, study_name):
    ea = event_accumulator.EventAccumulator(str(event_file), size_guidance={
        event_accumulator.SCALARS: 0,
        event_accumulator.IMAGES: 0,
    })
    try:
        ea.Reload()
    except Exception as e:
        print(f"Could not load {event_file}: {e}")
        return
    # Scalars
    for tag in ea.Tags().get('scalars', []):
        for scalar_event in ea.Scalars(tag):
            con.execute(
                "INSERT INTO scalars VALUES (?, ?, ?, ?, ?)",
                [study_name, tag, scalar_event.step, scalar_event.wall_time, scalar_event.value]
            )
    # Images
    for tag in ea.Tags().get('images', []):
        for img_event in ea.Images(tag):
            # Detect image format using PIL
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(img_event.encoded_image_string))
                img_format = img.format or "unknown"
            except Exception:
                img_format = "unknown"
            con.execute(
                "INSERT INTO images VALUES (?, ?, ?, ?, ?, ?)",
                [study_name, tag, img_event.step, img_event.wall_time, img_format, img_event.encoded_image_string]
            )

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Import TensorBoard event files to DuckDB')
    parser.add_argument('--mode', choices=['reset', 'append'], required=True,
                       help='Mode: reset (drop all tables) or append (add to existing data)')
    args = parser.parse_args()
    
    # Set up database based on mode
    setup_database(args.mode)
    
    # Process event files
    for subdir in RUNS_DIR.iterdir():
        if not subdir.is_dir():
            continue
        study_name = subdir.name
        for event_file in subdir.glob('events.out.tfevents.*'):
            print(f"Processing {event_file}")
            process_event_file(event_file, study_name)
    
    print(f"Done. Data imported to {DUCKDB_FILE} in {args.mode} mode")

if __name__ == "__main__":
    main()
