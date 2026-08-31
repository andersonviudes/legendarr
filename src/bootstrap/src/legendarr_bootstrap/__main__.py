import uvicorn


def main() -> None:
    # log_config=None: skip uvicorn's own logging setup (its default dictConfig gives
    # "uvicorn"/"uvicorn.access" their own handlers+formatters, disables propagation to
    # root) so its access/startup logs flow through our `configure_logging()` instead —
    # same timestamped format as every other logger, and captured by the ring buffer that
    # backs the System page's log viewer.
    uvicorn.run("legendarr_bootstrap.app:app", host="0.0.0.0", port=8000, log_config=None)


if __name__ == "__main__":
    main()
