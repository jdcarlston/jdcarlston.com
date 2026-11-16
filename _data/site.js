const fs = require("fs");
const path = require("path");

module.exports = {
  name: "JD Carlston",
  url: "https://jdcarlston.com",
  description:
    "JD Carlston: engineering leader, facilitator and coach in Salt Lake City. Systems that ship, teams that deliver, and customers that buy.",
  email: "contact@red-thread-labs.com",
  year: new Date().getFullYear(),
  // The portrait shows only once assets/profile.jpg exists.
  hasPortrait: fs.existsSync(path.join(__dirname, "..", "assets", "profile.jpg")),
  series: {
    "world-class": {
      title: "What in the World Is World-Class Engineering?",
      blurb:
        "Measuring world-classiness, the human needs a team has to meet, and diversity as an attribute of survival in a complex system.",
    },
    apparel: {
      title: "My Learning Journey Through the Apparel Industry",
      blurb:
        "Understanding fashion as a CAIO, connecting the schema at every level, measuring what matters, and what to learn before building.",
    },
  },
};
