from pathlib import Path
import shutil
import sys

APP = Path("app.py")
BACKUP = Path("app.py.before_cache_fix")

if not APP.exists():
    raise SystemExit("app.py が見つかりません。Runaways_Nexus の直下で実行してください。")

text = APP.read_text(encoding="utf-8-sig")
original = text

needle = 'A3_HISTORY = BASE / "data" / "a3_history.csv"\n'
insert = (
    'A3_HISTORY = BASE / "data" / "a3_history.csv"\n'
    'RD_HISTORY = BASE / "data" / "rd" / "history_seed_2020_2026.csv.gz"\n'
)
if 'RD_HISTORY = BASE / "data" / "rd" / "history_seed_2020_2026.csv.gz"' not in text:
    if needle not in text:
        raise SystemExit("A3_HISTORY 定義を見つけられません。app.py の構造を確認してください。")
    text = text.replace(needle, insert, 1)

old_cache = """@st.cache_data(show_spinner=False)
def get_training():
    return load_training(DATA, A3_HISTORY)

@st.cache_data(show_spinner="血統マスタ読込中...")
def get_pedigree_masters():
    return load_masters()

@st.cache_data(show_spinner="Race Development履歴読込中...")
def get_rd_data():
    return load_rd_data()
"""

new_cache = """def _file_version(path: Path) -> int:
    try:
        stat = path.stat()
        return hash((stat.st_mtime_ns, stat.st_size))
    except FileNotFoundError:
        return 0


@st.cache_data(show_spinner=False)
def get_training(data_version: int, a3_version: int):
    return load_training(DATA, A3_HISTORY)


@st.cache_data(show_spinner="血統マスタ読込中...")
def get_pedigree_masters():
    return load_masters()


@st.cache_data(show_spinner="Race Development履歴読込中...")
def get_rd_data(history_version: int):
    return load_rd_data()
"""

if 'def _file_version(path: Path) -> int:' not in text:
    if old_cache not in text:
        raise SystemExit("キャッシュ定義ブロックを見つけられません。app.py が想定版と異なる可能性があります。")
    text = text.replace(old_cache, new_cache, 1)

old_df = 'df = get_training()\n'
new_df = """df = get_training(
    _file_version(DATA),
    _file_version(A3_HISTORY),
)
"""
if old_df in text:
    text = text.replace(old_df, new_df, 1)

text = text.replace(
    'hist, rd_course, thresholds = get_rd_data()',
    'hist, rd_course, thresholds = get_rd_data(_file_version(RD_HISTORY))'
)
text = text.replace(
    'hist, _, _ = get_rd_data()',
    'hist, _, _ = get_rd_data(_file_version(RD_HISTORY))'
)

if 'get_rd_data()' in text:
    raise SystemExit("引数なし get_rd_data() が残っています。自動置換を中止しました。")

if text == original:
    print("変更なし：すでにキャッシュ対策済みの可能性があります。")
    sys.exit(0)

if not BACKUP.exists():
    shutil.copy2(APP, BACKUP)

APP.write_text(text, encoding="utf-8")
print("OK: app.py にCSV自動再読込対策を適用しました。")
print(f"Backup: {BACKUP}")
print("")
print("次に確認:")
print('  Select-String -Path .\\app.py -Pattern "RD_HISTORY|_file_version|get_training\\(|get_rd_data\\("')
print("")
print("Git反映:")
print("  git add app.py")
print('  git commit -m "Fix Streamlit data cache refresh"')
print("  git pull --rebase origin main")
print("  git push")
