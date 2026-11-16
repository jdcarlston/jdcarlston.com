# jdcarlston.com

Source for [jdcarlston.com](https://jdcarlston.com), the personal site of JD Carlston: engineering leader, facilitator and Human Engineer.

## What's here

- `index.njk`: the homepage.
- `essays/`: one Markdown file per engineering essay, plus their images. Each becomes a page at `/essays/<name>/`.
- `_includes/`: page layouts (`base.njk`, `essay.njk`) and shared pieces.
- `_data/`: site details, and `hero.js`, which draws the homepage's woven lattice and fiberglass at build time.
- `assets/`: the stylesheet, favicon and profile photo.
- `scripts/medium_import.py`: the tool that converted the Medium export.

The site is built with [Eleventy](https://www.11ty.dev/). Poetry and other writing imported from Medium stays out of this repo; it belongs to [Madder Craft](https://maddercraft.com) and [Red Thread Labs](https://red-thread-labs.com).

## Working on it

```bash
npm install      # once, to get Eleventy
npm start        # builds the site and serves it at http://localhost:8080, rebuilding on every save
npm run build    # builds the site into _site/
```

## Deploying

Every push to `main` deploys through Netlify, which runs `npm run build` and publishes `_site/` (see `netlify.toml`).

## Related

- [Red Thread Labs](https://red-thread-labs.com)
- [LinkedIn](https://www.linkedin.com/in/jdcarlston)
