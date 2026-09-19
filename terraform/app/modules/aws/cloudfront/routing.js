function handler(event) {
    var request = event.request;
    if (request.method !== 'GET' && request.method !== 'HEAD') {
        return request;
    }

    // Inspect encoded paths without changing asset keys or API requests.
    var path;
    try {
        path = decodeURIComponent(request.uri);
    } catch (error) {
        return request;
    }

    var reserved = ['/api', '/graphql', '/assets', '/static', '/.well-known'];
    for (var i = 0; i < reserved.length; i++) {
        if (path === reserved[i] || path.indexOf(reserved[i] + '/') === 0) {
            return request;
        }
    }

    // Files (including missing JS/CSS) must reach S3 and retain error status.
    if (path.indexOf('.') === -1) {
        request.uri = '/index.html';
    }
    return request;
}
