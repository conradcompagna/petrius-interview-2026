# Publish the viewer on GitHub Pages

The static viewer is in `site/`. It uses HTML, CSS, JavaScript and saved data files; it has no Python server, model process, login or API key. Finished collections appear first and earlier experiments remain in the collapsed archive.

The repository remains private until the author releases it. The publishing workflow explicitly skips private repositories.

When ready to publish:

1. Make `conradcompagna/petrius-interview-2026` public in the repository settings.
2. Under **Settings → Pages → Build and deployment**, choose **GitHub Actions**.
3. Under **Actions → Publish annotation viewer**, click **Run workflow** on `main`.

The resulting address will be **https://conradcompagna.github.io/petrius-interview-2026/**. Later changes to `site/` publish automatically.

To preview the same site locally, run `python -m http.server 8880 --directory site` from the package directory and open `http://localhost:8880/`. Open it through HTTP so the browser can load the saved data files.

Page annotations are compressed individually and decompressed in the browser. Images are linked to their library sources. Each overlay retains the original page coordinate system. The author's separate offline archive contains saved image copies; it is retained locally.

GitHub Free supports Pages from public repositories; GitHub limits a published site to 1 GB. The supplied workflow checks every local page reference and the total site size before publishing. See [GitHub Pages availability](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [size limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) and [the official workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
