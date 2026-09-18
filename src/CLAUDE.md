# JavaScript/Frontend-Specific Claude Instructions

This file contains JavaScript, TypeScript, and frontend-specific instructions for Claude Code when working on the OpenForge Catalog frontend.

## JavaScript/TypeScript Tests
Always run these after making changes to frontend code:
```bash
npm test                      # Run Jest tests
npm run lint:all             # Run ESLint and TypeScript type checking
```

## Key File Locations
- Frontend components: `src/components/`
- Admin interface: `src/components/admin/`
- Context providers: `src/contexts/`
- Type definitions: `src/types/`

## Frontend Technology Stack
- **Frontend uses Next.js 13** with app directory structure
- React app compiled statically (no Next.js SSR), served from S3
- Static frontend means no server-side rendering or API routes in Next.js

## JavaScript/TypeScript/CSS Preferences

### 1. Shield from complexity
- **CSS**: Handle styling details - Devon finds CSS anti-human
- **TypeScript**: Manage type annotations and interfaces
- **Goal**: Let Devon focus on functionality, not type gymnastics or style tweaking
- **Practical approach**: Keep frontend code simple and maintainable

### 2. Frontend philosophy
- JavaScript is a necessary tool, not a beloved language
- Prefer simple, working solutions over "clever" JavaScript
- Minimize frontend complexity where possible
- Backend (Python) is where the real logic should live

### 3. React & State Management
- **React is good**: Component abstraction makes sense (similar to server-side templating)
- **Redux was fine**: The unidirectional data flow is logical
- **Using Zustand**: Adopted because it's current best practice, not preference
- **Background**: Rails/ColdFusion experience - prefer clear MVC-style patterns
- **Keep it simple**: Use state management like server-side sessions - straightforward and predictable

### 4. Frontend Testing & API Patterns
- **Testing**: No religious preferences - pragmatic approach
- **API calls**: Session management handled automatically by backend
- **No explicit session checks**: Backend returns 401 if session invalid
- **Simple fetch patterns**: No need for complex API abstraction layers

### 5. Frontend Development Approach
- **Error handling**: Just console.log for now (beta phase) - tighten for 1.0
- **Loading states**: Keep it simple until users complain
- **Progressive enhancement**: Start minimal, add polish based on feedback
- **Data fetching**: No overengineering - just fetch() is fine
- **Caching philosophy**: "There are 2 hard things in programming: naming things, caching, and off by one errors" - avoid caching complexity where possible

## Development Notes
- **Hot reloading**: Frontend runs in development mode with hot-reloading enabled
- Changes to code are automatically picked up without needing to restart Next.js
