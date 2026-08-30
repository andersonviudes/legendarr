from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.languages import SUPPORTED_LANGUAGES
from legendarr_web.media_library import service
from legendarr_web.subtitle_acquisition import service as subtitle_acquisition_service
from legendarr_web.subtitle_acquisition.provider_display import provider_label
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/media")
templates = get_templates("media_library")


# The search panels auto-fire their results request on load (no more "Search" button), so
# the loading state names the providers being queried instead of a bare "Searching...".
async def _searching_providers(client: httpx.AsyncClient) -> list[str]:
    try:
        providers = await subtitle_acquisition_service.list_subtitle_providers(client)
    except httpx.HTTPStatusError:
        return []
    return [provider_label(p["kind"]) for p in providers if p["enabled"]]


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


@router.post("/movies/{movie_id}/search-subtitles")
async def trigger_movie_subtitle_search(
    request: Request, movie_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.trigger_movie_subtitle_search(client, movie_id)
        result = {"success": True, "message": "Subtitle search started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the subtitle search."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/series/{series_id}/search-subtitles")
async def trigger_series_subtitle_search(
    request: Request, series_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.trigger_series_subtitle_search(client, series_id)
        result = {"success": True, "message": "Subtitle search started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the subtitle search."}
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
async def show_subtitle_search(
    request: Request,
    media_file_id: int,
    language: str | None = None,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    # A subtitle's own "Search" pill action passes its language to search just that one
    # upgrade — matched case-insensitively against SUPPORTED_LANGUAGES since a subtitle's
    # stored `language` casing isn't guaranteed to match the canonical form providers
    # expect. No language (the file-level "Manual search" pill item and Actions-column
    # button) or an unrecognized one falls back to every target language of the file's
    # language profile — there's no picker for the user to fall back on instead anymore.
    canonical_language = next(
        (code for code, _ in SUPPORTED_LANGUAGES if language and code.lower() == language.lower()),
        None,
    )
    if canonical_language:
        languages = [canonical_language]
    else:
        try:
            languages = await service.get_target_languages(client, media_file_id)
        except httpx.HTTPStatusError:
            languages = []
    try:
        resource = await service.get_subtitle_search_resource(client, media_file_id)
    except httpx.HTTPStatusError:
        resource = None
    providers = await _searching_providers(client) if languages else []
    return templates.TemplateResponse(
        request,
        "_subtitle_search_panel.html",
        {
            "media_file_id": media_file_id,
            "languages": languages,
            "resource": resource,
            "providers": providers,
        },
    )


@router.get("/files/{media_file_id}/subtitle-search/results")
async def show_subtitle_search_results(
    request: Request,
    media_file_id: int,
    languages: Annotated[list[str] | None, Query()] = None,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    candidates = []
    for language in languages or []:
        try:
            found = await service.search_subtitle_candidates(client, media_file_id, language)
        except httpx.HTTPStatusError:
            found = []
        for candidate in found:
            candidate["target_language"] = language
        candidates.extend(found)
    return templates.TemplateResponse(
        request,
        "_subtitle_search_results.html",
        {"media_file_id": media_file_id, "candidates": candidates},
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


# === Series episodes with no `MediaFile` yet — same shape as the routes above, keyed
# by series/season/episode instead of a media file id. See `PendingSubtitle`'s
# backend docstring for why.


@router.get("/series/{series_id}/episodes/{season_number}/{episode_number}/subtitle-search")
async def show_pending_subtitle_search(
    request: Request,
    series_id: int,
    season_number: int,
    episode_number: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        languages = await service.get_pending_episode_target_languages(
            client, series_id, season_number, episode_number
        )
    except httpx.HTTPStatusError:
        languages = []
    providers = await _searching_providers(client) if languages else []
    return templates.TemplateResponse(
        request,
        "_pending_subtitle_search_panel.html",
        {
            "series_id": series_id,
            "season_number": season_number,
            "episode_number": episode_number,
            "languages": languages,
            "providers": providers,
        },
    )


@router.get("/series/{series_id}/episodes/{season_number}/{episode_number}/subtitle-search/results")
async def show_pending_subtitle_search_results(
    request: Request,
    series_id: int,
    season_number: int,
    episode_number: int,
    languages: Annotated[list[str] | None, Query()] = None,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    candidates = []
    for language in languages or []:
        try:
            found = await service.search_pending_subtitle_candidates(
                client, series_id, season_number, episode_number, language
            )
        except httpx.HTTPStatusError:
            found = []
        for candidate in found:
            candidate["target_language"] = language
        candidates.extend(found)
    return templates.TemplateResponse(
        request,
        "_pending_subtitle_search_results.html",
        {
            "series_id": series_id,
            "season_number": season_number,
            "episode_number": episode_number,
            "candidates": candidates,
        },
    )


@router.post(
    "/series/{series_id}/episodes/{season_number}/{episode_number}/subtitle-candidates/download"
)
async def download_pending_subtitle_candidate(
    request: Request,
    series_id: int,
    season_number: int,
    episode_number: int,
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
        result = await service.download_pending_subtitle_candidate(
            client, series_id, season_number, episode_number, candidate
        )
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't download the subtitle."}
    return templates.TemplateResponse(
        request, "_pending_subtitle_acquire_result.html", {"result": result}
    )


@router.get("/series/{series_id}/episodes/{season_number}/{episode_number}/subtitle-upload")
async def show_pending_subtitle_upload(
    request: Request, series_id: int, season_number: int, episode_number: int
):
    return templates.TemplateResponse(
        request,
        "_pending_subtitle_upload_panel.html",
        {
            "series_id": series_id,
            "season_number": season_number,
            "episode_number": episode_number,
            "languages": SUPPORTED_LANGUAGES,
        },
    )


@router.post("/series/{series_id}/episodes/{season_number}/{episode_number}/subtitle-upload")
async def upload_pending_subtitle(
    request: Request,
    series_id: int,
    season_number: int,
    episode_number: int,
    language: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's own multipart dependency idiom
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    content = await file.read()
    try:
        result = await service.upload_pending_subtitle(
            client,
            series_id,
            season_number,
            episode_number,
            language,
            file.filename or "subtitle",
            content,
        )
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't upload the subtitle."}
    return templates.TemplateResponse(
        request, "_pending_subtitle_acquire_result.html", {"result": result}
    )
