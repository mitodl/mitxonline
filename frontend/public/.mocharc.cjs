module.exports = {
    require: [
        "core-js",
        "regenerator-runtime",
        "@babel/register"
    ],
    // these need to be here because mocha doesn't provide
    // hooks like beforeEach when the file is --require
    file: [
        "src/tests_init.js"
    ]
}
