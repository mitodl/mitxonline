import { checkFeatureFlag } from "../lib/util"
import("../../scss/layout.scss")

if (checkFeatureFlag("mitxonline-new-featured-carousel")) {
  import("../../scss/featured-product-cards.scss")
}

if (checkFeatureFlag("mitxonline-new-product-page")) {
  import("../../scss/meta-product-page.scss")
}
