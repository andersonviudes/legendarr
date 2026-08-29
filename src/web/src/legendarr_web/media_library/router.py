import httpx
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.languages import SUPPORTED_LANGUAGES
from legendarr_web.media_library import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/media")
templates = get_templates("media_library")


@router.get("/movies")
async def show_movies(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    movies = await service.list_movies(client)
    await service.ensure_posters_cached(client, movies, "movie")
    return templates.TemplateResponse(request, "movies.html", {"movies": movies})


@router.get("/series")
async def show_series(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    series = await service.list_series(client)
    await service.ensure_posters_cached(client, series, "series")
    return templates.TemplateResponse(request, "series.html", {"series": series})


@router.get("/search")
async def search_media(
    request: Request, q: str = "", client: httpx.AsyncClient = Depends(get_backend_client)
):
    query = q.strip()
    results = await service.search_media(client, query) if query else []
    return templates.TemplateResponse(
        request, "_search_results.html", {"results": results, "query": query}
    )


@router.get("/wanted")
async def show_wanted(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    wanted = await service.list_wanted(client)
    await service.ensure_wanted_posters_cached(client, wanted)
    return templates.TemplateResponse(request, "wanted.html", {"wanted": wanted})


@router.get("/wanted/movies")
async def show_wanted_movies(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    wanted = await service.list_wanted(client)
    movies = [item for item in wanted if item["kind"] == "movie"]
    await service.ensure_posters_cached(client, movies, "movie")
    return templates.TemplateResponse(request, "wanted.html", {"wanted": movies})


@router.get("/wanted/series")
async def show_wanted_series(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    wanted = await service.list_wanted(client)
    series = [item for item in wanted if item["kind"] == "series"]
    await service.ensure_posters_cached(client, series, "series")
    return templates.TemplateResponse(request, "wanted.html", {"wanted": series})


@router.get("/movies/{movie_id}")
async def show_movie(
    request: Request, movie_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        movie = await service.get_movie(client, movie_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/media/movies", status_code=303)
    await service.ensure_poster_cached(client, movie, "movie")
    return templates.TemplateResponse(request, "movie_detail.html", {"movie": movie})


@router.get("/series/{series_id}")
async def show_series_item(
    request: Request, series_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        series = await service.get_series_item(client, series_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/media/series", status_code=303)
    await service.ensure_poster_cached(client, series, "series")
    return templates.TemplateResponse(request, "series_detail.html", {"series": series})


@router.post("/sync")
async def trigger_sync(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    try:
        await service.trigger_sync(client)
        result = {"success": True, "message": "Library sync started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the library sync."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/movies/{movie_id}/scan")
async def trigger_movie_scan(
    request: Request, movie_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.trigger_movie_scan(client, movie_id)
        result = {"success": True, "message": "Disk scan started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the disk scan."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/series/{series_id}/scan")
async def trigger_series_scan(
    request: Request, series_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.trigger_series_scan(client, series_id)
        result = {"success": True, "message": "Disk scan started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the disk scan."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/files/{media_file_id}/translate")
async def trigger_file_translation(
    request: Request,
    media_file_id: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.trigger_file_translation(client, media_file_id)
        result = {"success": True, "message": "Translation queued."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't queue the translation."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/subtitles/{subtitle_id}/sync-timing")
async def trigger_subtitle_timing_sync(
    request: Request,
    subtitle_id: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.trigger_subtitle_timing_sync(client, subtitle_id)
        result = {"success": True, "message": "Timing sync queued."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't queue the timing sync."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/subtitles/{subtitle_id}/translate")
async def trigger_subtitle_source_translation(
    request: Request,
    subtitle_id: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.trigger_subtitle_translation(client, subtitle_id)
        result = {"success": True, "message": "Translation queued."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't queue the translation."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/subtitles/{subtitle_id}/blacklist")
async def trigger_subtitle_blacklist(
    request: Request,
    subtitle_id: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.blacklist_subtitle(client, subtitle_id)
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't blacklist the subtitle."}
    return templates.TemplateResponse(
        request,
        "_subtitle_blacklist_result.html",
        {"media_file_id": result.get("media_file_id"), "result": result},
    )


@router.post("/subtitles/{subtitle_id}/remove-style-tags")
async def trigger_subtitle_style_tag_removal(
    request: Request,
    subtitle_id: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        response = await service.remove_subtitle_style_tags(client, subtitle_id)
        if response.get("status") == "cleaned":
            result = {"success": True, "message": "Style tags removed."}
        else:
            result = {"success": False, "message": "This subtitle's format isn't supported yet."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't remove style tags."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.get("/files/{media_file_id}/subtitle-search")
async def show_subtitle_search(request: Request, media_file_id: int, language: str | None = None):
    # A subtitle's own "Search" pill action passes its language so the panel opens with
    # that language pre-picked (search for an upgrade for THIS subtitle) instead of the
    # blank default the file-level "Manual search" action uses. Matched case-insensitively
    # against SUPPORTED_LANGUAGES since a subtitle's stored `language` casing isn't
    # guaranteed to match the option values (`select_field`'s `selected` comparison is
    # exact-match) — falls back to no pre-selection for an unrecognized code.
    selected_language = next(
        (code for code, _ in SUPPORTED_LANGUAGES if language and code.lower() == language.lower()),
        "",
    )
    return templates.TemplateResponse(
        request,
        "_subtitle_search_panel.html",
        {
            "media_file_id": media_file_id,
            "languages": SUPPORTED_LANGUAGES,
            "selected_language": selected_language,
        },
    )


@router.get("/files/{media_file_id}/subtitle-search/results")
async def show_subtitle_search_results(
    request: Request,
    media_file_id: int,
    language: str,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        candidates = await service.search_subtitle_candidates(client, media_file_id, language)
    except httpx.HTTPStatusError:
        candidates = []
    return templates.TemplateResponse(
        request,
        "_subtitle_search_results.html",
        {"media_file_id": media_file_id, "language": language, "candidates": candidates},
    )


@router.post("/files/{media_file_id}/subtitle-candidates/download")
async def download_subtitle_candidate(
    request: Request,
    media_file_id: int,
    provider: str = Form(...),
    release_name: str = Form(...),
    download_id: str = Form(...),
    language: str = Form(...),
    target_language: str = Form(...),
    page_link: str = Form(""),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    candidate = {
        "provider": provider,
        "release_name": release_name,
        "download_id": download_id,
        "language": language,
        "target_language": target_language,
        "page_link": page_link or None,
    }
    try:
        result = await service.download_subtitle_candidate(client, media_file_id, candidate)
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't download the subtitle.", "subtitles": []}
    return templates.TemplateResponse(
        request,
        "_subtitle_acquire_result.html",
        {"media_file_id": media_file_id, "result": result},
    )


@router.get("/files/{media_file_id}/subtitle-upload")
async def show_subtitle_upload(request: Request, media_file_id: int):
    return templates.TemplateResponse(
        request,
        "_subtitle_upload_panel.html",
        {"media_file_id": media_file_id, "languages": SUPPORTED_LANGUAGES},
    )


@router.post("/files/{media_file_id}/subtitle-upload")
async def upload_subtitle(
    request: Request,
    media_file_id: int,
    language: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's own multipart dependency idiom
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    content = await file.read()
    try:
        result = await service.upload_subtitle(
            client, media_file_id, language, file.filename or "subtitle", content
        )
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't upload the subtitle.", "subtitles": []}
    return templates.TemplateResponse(
        request,
        "_subtitle_acquire_result.html",
        {"media_file_id": media_file_id, "result": result},
    )
