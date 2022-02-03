import useSettings from "./settings"

describe("useSettings()", () => {
  it("returns the current settings", async () => {
    expect(useSettings()).toEqual(SETTINGS)
  })
})
