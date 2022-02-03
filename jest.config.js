module.exports = {
  setupFilesAfterEnv: [
    // see https://github.com/ricardo-ch/jest-fail-on-console/issues/4
    '@testing-library/react-hooks/disable-error-filtering.js',
    "<rootDir>static/js/test_setup.ts"
  ],
  cacheDirectory: ".jest-cache",
  transform: {    "^.+\\.(t|j)sx?$": ["@swc/jest"],  },
  moduleNameMapper: {
    "\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$":
      "<rootDir>/static/js/mocks/fileMock.js",
    "\\.(css|less)$": "<rootDir>/static/js/mocks/styleMock.js"
  },
  testPathIgnorePatterns: ["<rootDir>/staticfiles/", "<rootDir>/node_modules/"],
  testEnvironment: "jsdom"
}