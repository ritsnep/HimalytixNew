const path = require('path');
const TerserPlugin = require('terser-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const { WebpackManifestPlugin } = require('webpack-manifest-plugin');
const { SubresourceIntegrityPlugin } = require('webpack-subresource-integrity');

module.exports = {
  mode: 'production',
  entry: {
    main: './accounting/static/js/main.js',
    styles: './accounting/static/css/main.css'
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].[contenthash].js',
    crossOriginLoading: 'anonymous'
  },
  devtool: 'source-map',
  optimization: {
    minimize: true,
    minimizer: [new TerserPlugin()],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: '[name].[contenthash].css',
    }),
    new WebpackManifestPlugin(),
    new SubresourceIntegrityPlugin({
      hashFuncNames: ['sha256', 'sha384'],
    }),
  ],
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader'],
      },
    ],
  },
};