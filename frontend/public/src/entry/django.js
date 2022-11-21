// Third-party imports
import "jquery"
import "bootstrap"
import "video.js"
import "videojs-youtube/dist/Youtube"
import $ from "jquery"
$(".dates-tooltip").popover({
  sanitize: false,
  template:
    '<div class="popover" role="tooltip">' +
    '<div class="arrow"></div>' +
    '<div class="popover-header py-2 px-0 mx-5"></div>' +
    '<div class="popover-body"></div>' +
    "</div>"
})
$(".dates-tooltip").on("shown.bs.popover", () => {
  $(".date-link").attr("tabindex", 0)
  $(".date-link")
    .first()
    .focus()
  $(".date-link").on("click", () => {
    $(".dates-tooltip").popover("hide")
    $(".dates-tooltip").focus()
  })
})
