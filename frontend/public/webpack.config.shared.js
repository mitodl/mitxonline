const path = require("path")

module.exports = {
  config: {
    entry: {
      root:         "./src/entry/root",
      header:       "./src/entry/header",
      style:        "./src/entry/style",
      django:       "./src/entry/django",
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
      ]
    },
    resolve: {
      modules:    [
        path.join(__dirname, "src"),
        path.resolve(__dirname, "node_modules"),
        path.resolve(__dirname, "../../node_modules")
      ],
      extensions: [".js", ".jsx"]
    },
    performance: {
      hints: false
    }
  },
  babelSharedLoader: {
    test:    /\.jsx?$/,
    include: [
      path.resolve(__dirname, "src"),
      path.resolve(__dirname, "../../node_modules/query-string"),
      path.resolve(__dirname, "../../node_modules/strict-uri-encode"),
    ],
    loader:  "babel-loader",
    options:   {
      presets: [
        ["@babel/preset-env", { modules: false }],
        "@babel/preset-react",
        "@babel/preset-flow"
      ],
      plugins: [
        "@babel/plugin-transform-flow-strip-types",
        "react-hot-loader/babel",
        "@babel/plugin-proposal-object-rest-spread",
        "@babel/plugin-proposal-class-properties",
        "@babel/plugin-syntax-dynamic-import"
      ]
    }
  }
}
