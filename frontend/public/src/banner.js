/*eslint-env jquery*/
/*eslint semi: ["error", "always"]*/

function renderSiteBanner() {
  const bannerId = $(".banner").data("banner-id");
  if (bannerId) {
    if (localStorage.getItem("dismissedbanner") !== bannerId.toString()) {
      $(".banners").removeClass("d-none");
    }
  }
}

export default function banner() {
  renderSiteBanner();

  $(".banners").on("click", ".close-banner", function(e) {
    e.preventDefault();
    const $banner = $(this).closest(".banner");
    localStorage.setItem("dismissedbanner", $banner.data("banner-id"));
    $banner.remove();
  });
}
