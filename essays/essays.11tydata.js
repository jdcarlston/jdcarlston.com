// Every essay in this folder uses the essay layout and lives at /essays/<slug>/.
module.exports = {
  layout: "essay.njk",
  permalink: (data) => `/essays/${data.page.fileSlug}/`,
};
