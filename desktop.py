"""Same entry for manual source tests and the future Windows desktop build."""
import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()
    from src.desktop_app import main
    raise SystemExit(main())
