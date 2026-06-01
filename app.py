from __future__ import annotations

from dataclasses import asdict

from flask import Flask, jsonify, render_template, request

from ao3_client import SearchOptions, build_search_url, search_works

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/search")
def api_search():
    payload = request.get_json(silent=True) or {}
    options = SearchOptions(
        query=str(payload.get("query", "")),
        fandom=str(payload.get("fandom", "")),
        relationships=str(payload.get("relationships", "")),
        include_tags=str(payload.get("include_tags", "")),
        exclude_tags=str(payload.get("exclude_tags", "")),
        rating=str(payload.get("rating", "")),
        complete=str(payload.get("complete", "")),
        min_words=str(payload.get("min_words", "")),
        max_words=str(payload.get("max_words", "")),
        sort_column=str(payload.get("sort_column", "kudos_count")),
        sort_direction=str(payload.get("sort_direction", "desc")),
        pages=int(payload.get("pages", 1) or 1),
    )

    try:
        data = search_works(options)
    except Exception as exc:  # Keep the UI useful instead of exposing a traceback.
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
                "ao3_url": build_search_url(options, page=1),
                "options": asdict(options),
            }
        ), 502

    return jsonify(
        {
            "ok": True,
            "ao3_url": build_search_url(options, page=1),
            "options": asdict(options),
            **data,
        }
    )


@app.get("/api/preset/polytrix")
def polytrix_preset():
    options = SearchOptions(
        query='polytrix OR "Polyamorous Huntrix"',
        fandom="KPop Demon Hunters",
        relationships="Mira/Rumi/Zoey, Polyamorous Huntrix",
        include_tags="Fluff, Domestic Fluff, Established Relationship, Cuddling",
        exclude_tags="Angst, Hurt/Comfort, Heavy Angst, Major Character Death, Break Up",
        sort_column="kudos_count",
        sort_direction="desc",
        pages=2,
    )
    return jsonify({"options": asdict(options), "ao3_url": build_search_url(options)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
