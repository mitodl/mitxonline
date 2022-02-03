const webpack = require("webpack")
const path = require("path")
const R = require("ramda")
const BundleTracker = require("webpack-bundle-tracker")
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin
const { config } = require(path.resolve("./webpack.config.shared.js"))

const hotEntry = (host, port) =>
  `webpack-hot-middleware/client?path=http://${host}:${port}/__webpack_hmr&timeout=20000&reload=true`

const insertHotReload = (host, port, entries) =>
  R.map(
    R.compose(R.flatten, v => [v].concat(hotEntry(host, port))),
    entries
  )

const devConfig = Object.assign({}, config, {
  context: __dirname,
  mode: "development",
  devtool: "inline-source-map",
  output: {
    path: path.resolve("./static/bundles/"),
    filename: "[name].js"
  },
  plugins: [
    new webpack.HotModuleReplacementPlugin(),
    new BundleTracker({ filename: "./webpack-stats.json" }),
    new BundleAnalyzerPlugin()
  ],
  optimization: {
    moduleIds: 'named',
    splitChunks: {
      chunks: "all",
      minChunks: 2,
      cacheGroups: {
        common: {
          test: /[\\/]node_modules[\\/]/,
          name: 'common',
          chunks: 'all',
        },
      },
    },
    emitOnErrors: true
  },
})

devConfig.module.rules = [
  ...config.module.rules,
  {
    // this regex is necessary to explicitly exclude ckeditor stuff
    test: /static\/scss\/.+(\.css$|\.scss$)/,
    use: [
      { loader: "style-loader" },
      { loader: "css-loader?url=false" },
      { loader: "postcss-loader" },
      {
        loader: "sass-loader",
        options: {
          sassOptions: { quietDeps: true },
        },
      }
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