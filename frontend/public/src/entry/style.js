import { checkFeatureFlag } from "../lib/util"

if (checkFeatureFlag("jkachel-new-design")) {
  import("../../scss/layout-v2.scss")
} else {
  import("../../scss/layout.scss")
}
