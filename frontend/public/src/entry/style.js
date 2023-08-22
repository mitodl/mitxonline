import { checkFeatureFlag } from "../lib/util"

if (checkFeatureFlag("mitxonline-new-featured-carousel")) {
  import("../../scss/layout-v2.scss")
}
