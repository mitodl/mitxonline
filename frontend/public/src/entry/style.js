import { checkFeatureFlag } from "../lib/util"
import("../../scss/layout.scss")

if (checkFeatureFlag("mitxonline-new-product-page")) {
  import("../../scss/featured-product-cards.scss")
}
