A simple todo list application built with Flask for QA testing practice.

## API Endpoints for Testing

### Web Routes (HTML responses)
- GET `/` - Homepage with todo list
- POST `/add` - Add new todo
- GET `/toggle/<id>` - Toggle todo completion
- GET `/delete/<id>` - Delete todo
- GET `/edit/<id>` - Edit form
- POST `/edit/<id>` - Update todo
- GET `/stats` - Statistics page

### API Routes (JSON responses)
- GET `/api/todos` - Get all todos as JSON
- POST `/api/todos` - Create todo via JSON
- DELETE `/api/todos/<id>` - Delete todo via API