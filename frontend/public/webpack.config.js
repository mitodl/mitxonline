const path = require("path")
const webpack = require("webpack")
const BundleTracker = require("webpack-bundle-tracker")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")
const { BundleAnalyzerPlugin } = require("webpack-bundle-analyzer")

module.exports = function (env, argv) {
  const mode = argv.mode || process.env.NODE_ENV || "production"
  const isProduction = mode === "production"
  return {
    mode,
    context: __dirname,
    devtool: "source-map",
    entry: {
      root: "./src/entry/root",
      header: "./src/entry/header",
      style: "./src/entry/style",
      django: "./src/entry/django",
      requirementsAdmin: "./src/entry/requirements-admin"
    },
    output: {
      path: path.resolve(__dirname, "build"),
      ...(isProduction ? {
        filename: "[name]-[chunkhash].js",
        chunkFilename: "[id]-[chunkhash].js",
        crossOriginLoading: "anonymous",
        hashFunction: "xxhash64"
      } : {
        filename: "[name].js",
      }),
      publicPath: isProduction ? "/static/mitx-online/" : process.env.PUBLIC_PATH
    },
    module: {
      rules: [
        {
          test: /\.(svg|ttf|woff|woff2|eot|gif)$/,
          type: "asset/inline"
        },
        {
          test: require.resolve('jquery'),
          loader: "expose-loader",
          options: {
            exposes: ["jQuery", "$"]
          }
        },
        {
          test: /\.jsx?$/,
          include: [
            path.resolve(__dirname, "src"),
            path.resolve(__dirname, "../../node_modules/query-string"),
            path.resolve(__dirname, "../../node_modules/strict-uri-encode"),
          ],
          loader: "babel-loader",
        },
        {
          test: /\.css$|\.scss$/,
          use: [
            { loader: isProduction ? MiniCssExtractPlugin.loader : "style-loader" },
            "css-loader",
            "postcss-loader",
            "sass-loader"
          ]
        }
      ]
    },
    plugins: [
      new BundleTracker({
        filename: path.resolve(__dirname, "../../webpack-stats/default.json")
      })
    ].concat(isProduction ? [
      new webpack.LoaderOptionsPlugin({
        minimize: true
      }),
      new webpack.optimize.AggressiveMergingPlugin(),
      new MiniCssExtractPlugin({
        filename: "[name]-[contenthash].css"
      }),
      new BundleAnalyzerPlugin({
        analyzerMode: "static",
      })
    ] : []),
    resolve: {
      modules: [
        path.resolve(__dirname, "src"),
        path.resolve(__dirname, "node_modules"),
        path.resolve(__dirname, "../../node_modules")
      ],
      extensions: [".js", ".jsx"]
    },
    performance: {
      hints: false
    },
    optimization: {
      moduleIds: "named",
      splitChunks: {
        name: "common",
        minChunks: 2,
        ...(isProduction ? {
          cacheGroups: {
            common: {
              test: /[\\/]node_modules[\\/]/,
              name: 'common',
              chunks: 'all',
            }
          }
        } : {})
      },
      minimize: isProduction,
      emitOnErrors: false
    },
    devServer: {
      allowedHosts: "all",
      headers: {
        'Access-Control-Allow-Origin': '*'
      },
      host: "::",
      setupMiddlewares: function (middlewares, devServer) {
        if (!devServer) {
          throw new Error('webpack-dev-server is not defined')
        }

        devServer.app.get('/health', function (req, res) {
          res.json({ success: true, server: "webpack" })
        })

        return middlewares
      },
    }
  }
}
