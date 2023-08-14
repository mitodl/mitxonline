import { checkFeatureFlag } from "../lib/util"

if (checkFeatureFlag("mitxonline-new-product-page")) {
  import("../../scss/layout-v2.scss")
} else {
  import("../../scss/layout.scss")
}
