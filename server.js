const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 8080; // Use Render's provided port
const HOST = '0.0.0.0';

// This tells the server to serve all the files from a 'build' or 'public' folder
// *** IMPORTANT: Change 'build' to the name of your folder with HTML/CSS files ***
// If your HTML files are in the root, you might use 'public' or create a new folder.
app.use(express.static(path.join(__dirname, 'build')));

// For a Single-Page Application (like React), this sends the main index.html
// for any route that is not a static file.
app.get('/*', function (req, res) {
  res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

app.listen(PORT, HOST, () => {
  console.log(`Server is listening on http://${HOST}:${PORT}`);
});