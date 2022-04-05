const webpack = require("webpack")
const path = require("path")
const R = require("ramda")
const BundleTracker = require("webpack-bundle-tracker")
const { config, babelSharedLoader } = require(path.resolve(
  "./webpack.config.shared.js"
))

const hotEntry = (host, port) =>
  `webpack-hot-middleware/client?path=http://${host}:${port}/__webpack_hmr&timeout=20000&reload=true`

const insertHotReload = (host, port, entries) =>
  R.map(
    R.compose(
      R.flatten,
      v => [v].concat(hotEntry(host, port))
    ),
    entries
  )

const devConfig = Object.assign({}, config, {
  context: __dirname,
  mode:    "development",
  output:  {
    path: path.resolve(__dirname, "../../static/bundles/"),
    filename: "[name].js",
  },
  plugins: [
    new BundleTracker({ filename: path.resolve(__dirname, "../../webpack-stats.json") }),
    new webpack.HotModuleReplacementPlugin(),
  ],
  devtool:      "source-map",
  optimization: {
    moduleIds: "named",
    splitChunks:  {
      name:      "common",
      minChunks: 2
    },
    emitOnErrors: false
  }
})

devConfig.module.rules = [
  babelSharedLoader,
  ...config.module.rules,
  {
    test: /\.css$|\.scss$/,
    use:  [
      { loader: "style-loader" },
      { loader: "css-loader" },
      { loader: "postcss-loader" },
      { loader: "sass-loader" }
    ]
  }
]

const makeDevConfig = (host, port) =>
  Object.assign({}, devConfig, {
    entry: insertHotReload(host, port, devConfig.entry)
  })

module.exports = {
  makeDevConfig,
  devConfig
}
