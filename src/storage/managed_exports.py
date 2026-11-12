"""Refresh only canonical app-generated exports, archiving every replaced file."""
import json
import shutil
from pathlib import Path


def refresh_managed_exports(manager, state, backup_id):
    from src.exporters.md_exporter import export_living_journal_md, export_session_md, sanitize_filename
    from src.exporters.docx_exporter import export_living_journal_docx, export_session_docx

    backup_root = manager.get_campaign_dir(state["campaign_name"]) / "backups"
    before = json.loads((backup_root / backup_id).read_text(encoding="utf-8"))["campaign_state"]
    archive = backup_root / (backup_id + ".assets")
    safe = sanitize_filename(state["campaign_name"])
    slug = manager.sanitize_name(state["campaign_name"])
    current = {str(session["session_number"]): session for session in state.get("sessions", [])}
    numbers = {str(session["session_number"]) for session in before.get("sessions", [])} | set(current)
    result = {"updated": [], "archived": [], "errors": []}
    index = []

    def update(folder, label, filename, producer):
        target = folder / filename
        if not target.is_file():
            return
        if target.is_symlink() or not target.resolve().is_relative_to(folder.resolve()):
            result["errors"].append(f"No se modificó el enlace: {filename}")
            return
        original = archive / label / filename
        staged = archive / "staging" / label / filename
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, original)
            index.append({"folder": label, "filename": filename, "action": "archive" if producer is None else "replace"})
            if producer is None:
                target.unlink()
                result["archived"].append(filename)
            else:
                staged.parent.mkdir(parents=True, exist_ok=True)
                producer(staged)
                staged.replace(target)
                result["updated"].append(filename)
        except Exception as exc:
            result["errors"].append(f"{filename}: {exc}")

    folders = [(Path(manager.output_dir), "output"), (manager.get_campaign_dir(state["campaign_name"]) / "exports", "campaign_exports")]
    for folder, label in folders:
        if not folder.is_dir():
            continue
        update(folder, label, f"{safe}_Grimorio.md", lambda path: export_living_journal_md(state, output_path=str(path)))
        update(folder, label, f"{safe}_Grimorio.docx", lambda path: export_living_journal_docx(state, output_path=str(path)))
        for number in numbers:
            session = current.get(number)
            for suffix, coaching in (("", True), ("_Jugadores", False)):
                for extension, exporter in (("md", export_session_md), ("docx", export_session_docx)):
                    producer = None if session is None else lambda path, s=session, fn=exporter, clean=coaching: fn(
                        s, campaign_name=state["campaign_name"], roster=state.get("roster", []),
                        output_path=str(path), include_coaching=clean)
                    update(folder, label, f"{safe}_Sesion_{number}_Cronica{suffix}.{extension}", producer)
            producer = None if session is None else lambda path, s=session: path.write_text(s.get("raw_transcript") or s.get("transcript") or "", encoding="utf-8")
            update(folder, label, f"{slug}_sesion_{number}_transcripcion.txt", producer)
        latest = max(current.values(), key=lambda session: int(session["session_number"]), default=None)
        producer = None if latest is None else lambda path: path.write_text(latest.get("raw_transcript") or latest.get("transcript") or "", encoding="utf-8")
        update(folder, label, f"{slug}_transcripcion.txt", producer)
    if index:
        (archive / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
