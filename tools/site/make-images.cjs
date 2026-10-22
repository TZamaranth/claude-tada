// Renders the project's two images with a headless browser:
//   assets/social-preview.png (1280x640): the README banner and the image shown when
//     someone shares the home page link. A trimmed screenshot of index.html with the
//     dog-bark pad lit.
//   .claude-plugin/icon.png (1024x1024): the plugin icon, drawn by tools/site/icon.html.
//     Anthropic's plugin directory takes the icon from the first submission only.
//
// Usage (needs Playwright: npm install playwright && npx playwright install chromium):
//   python tools/make-site.py
//   node tools/site/make-images.cjs

const path = require("path");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");

const repositoryDirectory = path.resolve(__dirname, "..", "..");
const fileUrl = (...parts) =>
  pathToFileURL(path.join(repositoryDirectory, ...parts)).href;

const cardStyle = `
  body { zoom: 0.92; }
  .top nav, .section, footer, .sub, .bark-button, .install-note, .install-links, .device-note, .device-foot { display: none; }
  .hero .deck { margin-bottom: 28px; }
  .top { padding: 26px 0 0; }
  .hero { padding: 0; min-height: 600px; gap: 48px; }
  .hero h1 { margin-bottom: 28px; }
  .pads > :nth-child(n + 9) { display: none; }
`;

async function renderSocialPreview(browser) {
  const outputPath = path.join(
    repositoryDirectory,
    "assets",
    "social-preview.png",
  );
  const page = await browser.newPage({
    viewport: { width: 1280, height: 640 },
  });
  await page.goto(fileUrl("index.html"));
  await page.waitForLoadState("networkidle");
  await page.addStyleTag({ content: cardStyle });
  // Light the dog-bark pad to match the headline, and show it set for "done".
  // The button itself is hidden in the card layout, so click it from the page.
  await page.evaluate(() => {
    document.getElementById("play-bark").click();
    document.getElementById("lcd-event").textContent = "done";
    document.getElementById("lcd-command").textContent =
      "/tada:sound done dog-bark";
  });
  await page.waitForTimeout(300);
  await page.screenshot({ path: outputPath });
  console.log(`wrote ${outputPath}`);
}

async function renderIcon(browser) {
  const outputPath = path.join(
    repositoryDirectory,
    ".claude-plugin",
    "icon.png",
  );
  const page = await browser.newPage({
    viewport: { width: 1024, height: 1024 },
  });
  await page.goto(fileUrl("tools", "site", "icon.html"));
  await page.screenshot({ path: outputPath, omitBackground: true });
  console.log(`wrote ${outputPath}`);
}

async function main() {
  const browser = await chromium.launch({
    args: ["--autoplay-policy=no-user-gesture-required"],
  });
  try {
    await renderSocialPreview(browser);
    await renderIcon(browser);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error("could not render the images:", error);
  process.exit(1);
});
