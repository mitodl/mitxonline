// Third-party imports
import "jquery"
import "bootstrap"
import "video.js"
import "videojs-youtube/dist/Youtube"
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

document.addEventListener("DOMContentLoaded", function() {
  const prevButton = document.getElementById("featuredCarouselPrev")
  const nextButton = document.getElementById("featuredCarouselNext")
  const featuredCarouselElement = document.getElementById("featuredProductCarousel")
  const carouselInner = document.getElementsByClassName("carousel-inner")[0]

  prevButton.addEventListener("click", function() {
    setToPosition("prev")
  })
  nextButton.addEventListener("click", function() {
    setToPosition("next")
  })

  function setToPosition(direction) {
    const bootstrap = require("bootstrap")
    const featuredCarousel = bootstrap.Carousel.getInstance(featuredCarouselElement)
    const cardOffset = window.matchMedia("(max-width: 1199.98px)").matches ? 3 : window.matchMedia("(max-width: 991.98px)").matches ? 2 : window.matchMedia("(max-width: 767.98px)").matches ? 1 : 4
    const currentCard = carouselInner.getElementsByClassName("active")[0]
    const cardArray = Array.from(carouselInner.children)
    const currentPosition = cardArray.indexOf(currentCard)
    const numberOfCards = cardArray.length - 1
    let prevPosition = currentPosition - cardOffset
    prevPosition = prevPosition >= 0 ? prevPosition : 0
    let nextPosition = currentPosition + cardOffset
    nextPosition = currentPosition + cardOffset <= numberOfCards ? nextPosition : numberOfCards
    let toPosition = direction === "prev" ? prevPosition : nextPosition
    toPosition = toPosition.toString()
    console.log(toPosition)
    featuredCarousel.to(toPosition)
  }
})
