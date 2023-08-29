import { checkFeatureFlag } from "../lib/util"
import "../../scss/layout.scss"

if (checkFeatureFlag("mitxonline-new-featured-hero")) {
  import("../../scss/home-page-hero.scss")
}

if (checkFeatureFlag("mitxonline-new-home-page-video-component")) {
  import("../../scss/home-page-video-component.scss")
}

if (checkFeatureFlag("mitxonline-new-product-page")) {
  import("../../scss/meta-product-page.scss")
}
