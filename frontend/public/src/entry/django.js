// Third-party imports
import "jquery"
import "bootstrap"
import "video.js"
import "videojs-youtube/dist/Youtube"
import "slick-carousel"
import $ from "jquery"
$(document).ready(function() {
  $(".dates-tooltip").popover({
    sanitize: false,
    template:
      '<div class="popover" role="tooltip">' +
      '<div class="arrow"></div>' +
      '<div class="popover-header py-2 px-0 mx-5"></div>' +
      '<div class="popover-body"></div>' +
      "</div>"
  })
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

$(document).ready(function() {
  $(".carousel-content").slick({
    accessibility: true,
    arrows:        true,
    prevArrow:     $(".prev-button"),
    nextArrow:     $(".next-button"),
    focusOnChange: true,
    responsive:    [
      {
        breakpoint: 1025,
        settings:   {
          slidesToShow:   3,
          slidesToScroll: 3
        }
      },
      {
        breakpoint: 605,
        settings:   {
          slidesToShow:   2,
          slidesToScroll: 2
        }
      },
      {
        breakpoint: 480,
        settings:   {
          slidesToShow:   1,
          slidesToScroll: 1
        }
      }
    ],
    slidesToShow:   4,
    slidesToScroll: 4
  })
  $(".slick-slide").removeAttr("tabindex")

  $("body").scrollspy({ target: "#tab-bar" })
  $(".nav .nav-link").on("click", function() {
    $(".nav").find(".active").removeClass("active")
    $(this).addClass("active")
    $(".nav .dropdown-toggle").text($(this).text())
  })
})
