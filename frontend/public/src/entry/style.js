import { checkFeatureFlag } from "../lib/util"

if (checkFeatureFlag("mitxonline-new-home-page-video-component")) {
  import("../../scss/home-page-video-component.scss")
}
