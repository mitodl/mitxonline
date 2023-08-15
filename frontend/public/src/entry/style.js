import { checkFeatureFlag } from "../lib/util"

if (checkFeatureFlag("mitxonline-new-product-page")) {
  console.log("Success")
  import("../../scss/layout-v2.scss")
} else {
  console.log("not success")
  import("../../scss/layout.scss")
}
