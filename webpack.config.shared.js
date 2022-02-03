const path = require("path")
const webpack = require("webpack")

module.exports = {
  config: {
    entry: {
      root:         ["@babel/polyfill", "./static/js/entry/root"],
      header:       ["@babel/polyfill", "./static/js/entry/header"],
      style:        "./static/js/entry/style",
      django:       "./static/js/entry/django",
    },
    module: {
      rules: [
        {
          // this regex is necessary to explicitly exclude ckeditor stuff
          test: /static\/.+\.(svg|ttf|woff|woff2|eot|gif)$/,
          use: "url-loader"
        },
        {
          test: /node_modules\/react-nestable\/.+\.svg$/,
          use: "svg-inline-loader?classPrefix"
        },
        {
          test: /node_modules\/react-nestable\/dist\/styles\/.+\.css/,
          loader: "style-loader"
        },
        {
          test: /\.tsx?$/,
          use: "swc-loader",
          exclude: /node_modules/
        },
        {
          test: /ckeditor5-[^/\\]+[/\\]theme[/\\]icons[/\\][^/\\]+\.svg$/,
          use: ["raw-loader"]
        },
        {
          test: /ckeditor5-[^/\\]+[/\\]theme[/\\].+\.css$/,
          use: [
            {
              loader: "style-loader",
              options: {
                injectType: "singletonStyleTag",
              }
            },
            "css-loader",
            "postcss-loader"
          ]
        }
      ]
    },
    resolve: {
      modules: [path.join(__dirname, "static/js"), "node_modules"],
      extensions: [".js", ".jsx", ".ts", ".tsx"]
    },
    performance: {
      hints: false
    }
  }
}