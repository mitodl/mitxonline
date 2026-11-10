// @flow
// The CMS product and home pages render a video.js player from the JSON that
// cms.models.video_player_config puts in data-setup. These tests load the same
// modules as entry/django.js and build players from both config shapes, so an
// upgrade of video.js or its dependencies (http-streaming, mpd-parser, xmldom)
// that breaks loading or player setup fails here.
import { assert } from "chai"
import sinon from "sinon"
import videojs from "video.js"

const YOUTUBE_CONFIG = {
  techOrder: ["youtube", "html5"],
  sources:   [
    { src: "https://www.youtube.com/watch?v=abc123", type: "video/youtube" }
  ],
  controls: false,
  youtube:  { ytControls: 2, cc_load_policy: 1, cc_lang_pref: 1 }
}

const HTML5_CONFIG = {
  techOrder: ["html5"],
  sources:   [{ src: "https://example.com/video.mp4" }]
}

describe("video.js player setup", () => {
  let player, sandbox

  beforeEach(() => {
    // videojs-youtube 2.6.1 warns at import that videojs.extend is deprecated,
    // and jsdom can't play media, so the HTML5 tech reports an unsupported
    // source. Keep video.js quiet so js_test.sh's stderr check passes.
    videojs.log.level("off")
    require("videojs-youtube/dist/Youtube")
    sandbox = sinon.createSandbox()
    // jsdom doesn't implement load(), which video.js calls when it swaps techs.
    sandbox.stub(window.HTMLMediaElement.prototype, "load")
    // Same element as cms/templates/videojs_tag.html renders.
    if (document.body) {
      document.body.innerHTML =
        '<video-js id="test-player" class="vjs-default-skin vjs-big-play-centered" controls preload="metadata"></video-js>'
    }
  })

  afterEach(() => {
    if (player) {
      player.dispose()
      player = null
    }
    sandbox.restore()
    videojs.log.level("info")
  })

  it("registers the techs the CMS config names", () => {
    assert.isOk(videojs.getTech("Youtube"))
    assert.isOk(videojs.getTech("Html5"))
  })

  it("loads the HTTP streaming handler", () => {
    assert.isOk(videojs.Vhs)
  })
  ;[
    ["YouTube", YOUTUBE_CONFIG, false],
    ["HTML5", HTML5_CONFIG, true]
  ].forEach(([name, config, hasControls]) => {
    it(`builds a player from the ${name} config`, () => {
      player = videojs("test-player", config)

      assert.deepEqual(player.options_.techOrder, config.techOrder)
      assert.deepEqual(player.options_.sources, config.sources)
      assert.equal(player.controls(), hasControls)
    })
  })
})
