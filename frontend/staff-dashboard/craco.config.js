const CracoLessPlugin = require("craco-less");
const path = require("path");
const BundleTracker = require('webpack-bundle-tracker');
const { merge } = require("webpack-merge");

module.exports = {
  plugins: [
    {
      plugin: CracoLessPlugin,
      options: {
        lessLoaderOptions: {
          lessOptions: {
            javascriptEnabled: true,
          },
        },
      },
    },
    {
      plugin: {
        overrideWebpackConfig: ({ webpackConfig }) => {
          const mode = process.env.NODE_ENV || "production";
          const isProduction = mode === "production";
          const publicPath = isProduction ? "/static/staff-dashboard/" : process.env.PUBLIC_PATH;

          return merge(webpackConfig, {
            output: {
              publicPath
            },
            plugins: [
              new BundleTracker({
                filename: path.resolve(__dirname, "../../webpack-stats/staff-dashboard.json"),
              }),
            ],
            devServer: {
              setupMiddlewares: function (middlewares, devServer) {
                if (!devServer) {
                  throw new Error('webpack-dev-server is not defined');
                }

                devServer.app.get('/health', function (_req, res) {
                  res.json({ success: true, server: "webpack" });
                });

                return middlewares;
              },
            },
          });
        }
      }
    }
  ],
};