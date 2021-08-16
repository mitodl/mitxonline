// Third-party imports
import "jquery"
import "bootstrap"
import "popper.js"
import "slick-carousel"
import "hls.js"
import "video.js"
import "videojs-youtube/dist/Youtube"
import "@fancyapps/fancybox"

// Custom native imports
import notifications from "../notifications.js"
import tooltip from "../tooltip.js"

document.addEventListener("DOMContentLoaded", function() {
  notifications()
  tooltip()
})
