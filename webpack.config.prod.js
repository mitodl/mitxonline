const webpack = require("webpack")
const path = require("path")
const BundleTracker = require("webpack-bundle-tracker")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")
const { config } = require(path.resolve("./webpack.config.shared.js"))

const prodConfig = Object.assign({}, config)
prodConfig.module.rules = [
  ...config.module.rules,
  {
    // this regex is necessary to explicitly exclude ckeditor stuff
    test: /static\/scss\/.+(\.css$|\.scss$)/,
    use: [
      {
        loader: MiniCssExtractPlugin.loader
      },
      "css-loader?url=false",
      "postcss-loader",
      {
        loader: "sass-loader",
        options: {
          sassOptions: { quietDeps: true },
        },
      }
    ]
  }
]

module.exports = Object.assign(prodConfig, {
  context: __dirname,
  mode: "production",
  output: {
    path: path.resolve("./static/bundles/"),
    filename: "[name]-[chunkhash].js",
    chunkFilename: "[id]-[chunkhash].js",
    crossOriginLoading: "anonymous"
  },

  plugins: [
    new BundleTracker({
      filename: "./webpack-stats.json"
    }),
    new webpack.LoaderOptionsPlugin({
      minimize: true
    }),
    new webpack.optimize.AggressiveMergingPlugin(),
    new MiniCssExtractPlugin({
      filename: "[name]-[contenthash].css"
    })
  ],
  optimization: {
    minimize: true,
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
  },
  devtool: "source-map"
})