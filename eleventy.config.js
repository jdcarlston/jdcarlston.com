// Eleventy configuration for jdcarlston.com.
// Builds the homepage, the essays index and one page per essay into _site/.

const yaml = require("js-yaml");
const site = require("./_data/site.js");

// Essay pictures load from the Cloudflare media bucket on the live site once site.media.useBucket is on.
// While previewing (npm start), or with JDC_LOCAL_MEDIA=1, they load from essays/images/ instead.
const previewing = process.env.ELEVENTY_RUN_MODE === "serve";
const useBucket = site.media.useBucket && !previewing && process.env.JDC_LOCAL_MEDIA !== "1";

module.exports = function (eleventyConfig) {
  // Only the published site goes into the build. writing/ is the Medium
  // import staging area (poetry and essays for other sites live there),
  // scripts/ holds the import tool, and README.md is for GitHub.
  eleventyConfig.ignores.add("writing/**");
  eleventyConfig.ignores.add("scripts/**");
  eleventyConfig.ignores.add("README.md");
  eleventyConfig.ignores.add(".venv/**");
  eleventyConfig.ignores.add("netlify/**");
  eleventyConfig.ignores.add("_to_delete/**"); // old files waiting to be deleted

  // Data files can be YAML (_data/*.yml), which the site editor at /admin can read and write.
  eleventyConfig.addDataExtension("yml,yaml", (contents) => yaml.load(contents));

  // Every picture on the site (the essays' pictures in essays/images/ and the ones in assets/, like the
  // portrait and the icon) loads from the Cloudflare media bucket once site.media.useBucket is on,
  // at the same path (media.jdcarlston.com/essays/images/..., media.jdcarlston.com/assets/...).
  // Only the styles in assets/ still ship with the site then.
  const picture = /"\/((?:essays\/images|assets)\/[^"]+\.(?:png|jpe?g|gif|webp|avif|svg|ico))"/g;
  if (useBucket) {
    eleventyConfig.addPassthroughCopy("assets/*.css");
    eleventyConfig.addTransform("picturesFromMedia", (content, outputPath) =>
      outputPath && outputPath.endsWith(".html")
        ? content.replace(picture, (_, file) => `"${site.media.base}/${file}"`)
        : content);
  } else {
    eleventyConfig.addPassthroughCopy("assets");
    eleventyConfig.addPassthroughCopy("essays/images");
  }
  eleventyConfig.addPassthroughCopy("admin"); // the site editor at /admin (see admin/config.yml)

  // Poems and lists in the essays use single line breaks; keep them.
  eleventyConfig.amendLibrary("md", (md) => md.set({ breaks: true, html: true, typographer: true }));

  eleventyConfig.addCollection("essays", (api) =>
    api.getFilteredByGlob("essays/*.md").sort((a, b) => b.date - a.date)
  );

  eleventyConfig.addFilter("isoDate", (d) => new Date(d).toISOString().slice(0, 10));
  eleventyConfig.addFilter("monthYear", (d) =>
    new Date(d).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
  );
  eleventyConfig.addFilter("year", (d) => new Date(d).getUTCFullYear());

  // About 230 words a minute, never less than one.
  eleventyConfig.addFilter("readingTime", (html) => {
    const words = String(html).replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.round(words / 230));
  });

  // Give each <h2> an id so the contents list can link to it.
  const slugify = (s) =>
    s.replace(/<[^>]+>/g, "").toLowerCase().replace(/&[a-z]+;/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  eleventyConfig.addFilter("withHeadingIds", (html) =>
    String(html).replace(/<h2>(.*?)<\/h2>/g, (_, inner) => `<h2 id="${slugify(inner)}">${inner}</h2>`)
  );
  eleventyConfig.addFilter("toc", (html) =>
    [...String(html).matchAll(/<h2>(.*?)<\/h2>/g)].map((m) => ({
      id: slugify(m[1]),
      text: m[1].replace(/<[^>]+>/g, ""),
    }))
  );

  // The essay just before and after this one, by date.
  eleventyConfig.addFilter("neighbors", (all, url) => {
    const byDate = [...all].sort((a, b) => a.date - b.date);
    const i = byDate.findIndex((p) => p.url === url);
    return { earlier: byDate[i - 1], later: byDate[i + 1] };
  });

  eleventyConfig.addFilter("inSeries", (all, key) =>
    all.filter((p) => p.data.series === key).sort((a, b) => a.data.part - b.data.part)
  );

  eleventyConfig.addFilter("standalone", (all) => all.filter((p) => !p.data.series));

  return {
    dir: { input: ".", includes: "_includes", data: "_data", output: "_site" },
    markdownTemplateEngine: false,
    htmlTemplateEngine: "njk",
  };
};
