# Phase 5: Authentication System Implementation Plan

## Overview

This document outlines the implementation of Phase 5 - the Authentication System for the OpenForge Catalog. This phase introduces OAuth 2.0 authentication with Patreon and Google, user management functionality, session-based authentication, and role-based access control (RBAC).

## Phase 5: Authentication System Implementation

### Priority: HIGH
### Timeline: 3-4 weeks
### Dependencies: Phase 2 complete (Documentation System)

## Completed Implementation

### Database Schema Updates ✅

#### Users and Identity Tables
**Created users and user_identities tables:**
```sql
-- Users table for storing user accounts
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    role text NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    patreon_tier text,
    blocked boolean DEFAULT false,
    blocked_reason text,
    blocked_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- User identities for OAuth provider connections
CREATE TABLE user_identities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider IN ('patreon', 'google')),
    provider_id text NOT NULL,
    created_at timestamptz DEFAULT now(),
    UNIQUE(provider, provider_id)
);

-- Sessions table (extended from Phase 2)
-- Added user_id and csrf_token columns to existing sessions table
ALTER TABLE sessions ADD COLUMN user_id uuid REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE sessions ADD COLUMN csrf_token text NOT NULL;

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_blocked ON users(blocked);
CREATE INDEX idx_user_identities_user ON user_identities(user_id);
CREATE INDEX idx_user_identities_provider ON user_identities(provider, provider_id);
CREATE INDEX idx_sessions_user ON sessions(user_id);
```

### OAuth Integration ✅

#### Patreon OAuth Service
**Implemented full Patreon OAuth 2.0 flow with tier detection:**
```python
class PatreonOAuthService:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize Patreon OAuth service with v2 API support."""

    def get_authorization_url(self) -> str:
        """Generate Patreon authorization URL with required scopes."""
        # Scopes: identity[email], memberships

    def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access/refresh tokens."""

    def get_user_info_and_tier(self, access_token: str) -> dict:
        """Fetch user info and Patreon tier using v2 API."""
        # Returns: id, email, tier (Bronze/Silver/Gold/Platinum)

    def _determine_patreon_tier(self, member_data: dict) -> Optional[str]:
        """Determine user's Patreon tier from membership data."""
        # Maps cent amounts to tiers:
        # - 200: Bronze
        # - 500: Silver
        # - 1000: Gold
        # - 2000: Platinum
```

#### Google OAuth Service
**Implemented Google OAuth 2.0 flow:**
```python
class GoogleOAuthService:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize Google OAuth service."""

    def get_authorization_url(self) -> str:
        """Generate Google authorization URL."""
        # Scopes: openid, email, profile

    def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for tokens."""

    def get_user_info(self, access_token: str) -> dict:
        """Fetch user info from Google."""
        # Returns: id, email
```

### Session Management ✅

#### Enhanced Session Service
**Extended session service with user authentication:**
```python
class SessionService:
    def create_user_session(self, user_id: str) -> dict:
        """Create new user session with CSRF token."""
        # - Generates secure session token
        # - Creates CSRF token for protection
        # - 30-day expiration
        # - Returns session_token, csrf_token, expires_at

    def validate_session(self, session_token: str) -> Optional[dict]:
        """Validate session and return user data."""
        # - Checks expiration
        # - Verifies user not blocked
        # - Updates last_used_at (throttled)
        # - Returns session with user data

    def get_csrf_token_for_session(self, session_token: str) -> Optional[str]:
        """Get CSRF token for session validation."""
```

### Authentication API Endpoints ✅

#### OAuth Endpoints
```typescript
// Patreon OAuth flow
GET /api/auth/patreon
// Redirects to Patreon authorization

GET /api/auth/patreon/callback?code={code}
// Handles OAuth callback, creates user session
Response: {
  user: User,
  session_token: string,
  csrf_token: string,
  expires_at: string
}

// Google OAuth flow
GET /api/auth/google
// Redirects to Google authorization

GET /api/auth/google/callback?code={code}
// Handles OAuth callback, creates user session
Response: {
  user: User,
  session_token: string,
  csrf_token: string,
  expires_at: string
}

// Logout
POST /api/auth/logout
Headers: { Authorization: Bearer <session_token> }
Response: { message: "Logged out successfully" }

// Current user
GET /api/auth/me
Headers: { Authorization: Bearer <session_token> }
Response: { user: User }
```

### User Management CRUD ✅

#### User Service Implementation
```python
class UserService:
    def get_users(self, limit=100, offset=0, search=None,
                  role=None, blocked=None, patreon_tier=None) -> dict:
        """Get paginated user list with filters."""

    def get_user_by_id(self, user_id: str) -> dict:
        """Get user with identities."""

    def update_user(self, user_id: str, role=None,
                   patreon_tier=None, blocked=None,
                   blocked_reason=None) -> dict:
        """Update user properties."""

    def delete_user(self, user_id: str) -> bool:
        """Delete user and cascade to identities/sessions."""

    def get_user_sessions(self, user_id: str) -> List[dict]:
        """Get user's active sessions."""

    def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all user sessions."""
```

#### User Management Endpoints
```typescript
// List users (admin only)
GET /api/users?limit=100&offset=0&search=email&role=admin&blocked=false
Headers: { Authorization: Bearer <session_token> }
Response: {
  users: User[],
  total: number,
  limit: number,
  offset: number
}

// Get user (admin or own profile)
GET /api/users/{user_id}
Headers: { Authorization: Bearer <session_token> }
Response: User

// Update user (admin only)
PATCH /api/users/{user_id}
Headers: {
  Authorization: Bearer <session_token>,
  X-CSRF-Token: <csrf_token>
}
Body: {
  role?: 'user' | 'admin',
  patreon_tier?: 'Bronze' | 'Silver' | 'Gold' | 'Platinum',
  blocked?: boolean,
  blocked_reason?: string
}
Response: User

// Delete user (admin only, cannot self-delete)
DELETE /api/users/{user_id}
Headers: {
  Authorization: Bearer <session_token>,
  X-CSRF-Token: <csrf_token>
}
Response: { message: "User deleted successfully" }

// Block user (admin only)
POST /api/users/{user_id}/block
Headers: {
  Authorization: Bearer <session_token>,
  X-CSRF-Token: <csrf_token>
}
Body: { reason: string }
Response: {
  user: User,
  sessions_revoked: number
}

// Unblock user (admin only)
POST /api/users/{user_id}/unblock
Headers: {
  Authorization: Bearer <session_token>,
  X-CSRF-Token: <csrf_token>
}
Response: User

// Get user sessions (admin or own)
GET /api/users/{user_id}/sessions
Headers: { Authorization: Bearer <session_token> }
Response: { sessions: Session[] }

// Revoke user sessions (admin or own)
DELETE /api/users/{user_id}/sessions
Headers: {
  Authorization: Bearer <session_token>,
  X-CSRF-Token: <csrf_token>
}
Response: {
  message: string,
  count: number
}
```

### Authentication Middleware ✅

#### Session-Based Authentication
```python
def authenticate(methods=None):
    """Decorator for protecting routes with session auth."""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            # Extract session token from Authorization header
            # Validate session and attach to g.session
            # Check if user is blocked
            # Proceed if valid, return 401 if not
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

#### CSRF Protection
```python
def csrf_protect(f):
    """Decorator for CSRF protection on state-changing operations."""
    def decorated_function(*args, **kwargs):
        # Verify X-CSRF-Token header matches session
        # Return 403 if invalid
        return f(*args, **kwargs)
    return decorated_function
```

### Testing ✅

#### Unit Tests
- OAuth service tests (Patreon and Google)
- Session service tests
- User service tests
- Authentication middleware tests
- CSRF protection tests

#### Integration Tests
- Full OAuth flow tests
- User management API tests
- Session lifecycle tests
- Role-based access tests
- User blocking flow tests

## Remaining Implementation

### 6. Role-Based Access Control for Existing Endpoints 🔧

**Update existing endpoints to respect user roles:**

#### Blueprint and Tag Endpoints
```python
# Current: API key only
# Required: API key OR (session + admin role)

@blueprints_bp.route("/blueprints", methods=["POST"])
@authenticate(methods=["POST"])  # Add session auth
@csrf_protect  # Add CSRF protection
def create_blueprint():
    # Check for admin role or API key
    if not has_api_key() and g.session["user"]["role"] != "admin":
        raise Forbidden()
```

#### Documentation Endpoints
```python
# Update all POST/PUT/DELETE documentation endpoints
# to accept session authentication with admin role
```

#### Image Management Endpoints
```python
# Update admin image endpoints to accept session auth
# Maintain backward compatibility with API keys
```

### 7. Frontend Authentication Components 🔧

**Create React components for authentication:**

#### Login Page Component
```typescript
const LoginPage = () => {
  return (
    <div className="login-container">
      <h1>Sign In to OpenForge Catalog</h1>

      <div className="oauth-buttons">
        <a href="/api/auth/patreon" className="patreon-login">
          <PatreonIcon />
          Sign in with Patreon
        </a>

        <a href="/api/auth/google" className="google-login">
          <GoogleIcon />
          Sign in with Google
        </a>
      </div>

      <div className="login-benefits">
        <h3>Patreon Supporters Get:</h3>
        <ul>
          <li>Early access to new models</li>
          <li>Exclusive blueprint collections</li>
          <li>Priority support</li>
        </ul>
      </div>
    </div>
  );
};
```

#### Auth Context Provider
```typescript
interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (provider: 'patreon' | 'google') => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check authentication on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('session_token');
    if (!token) {
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
      } else {
        localStorage.removeItem('session_token');
        localStorage.removeItem('csrf_token');
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    }

    setIsLoading(false);
  };

  const login = (provider: 'patreon' | 'google') => {
    window.location.href = `/api/auth/${provider}`;
  };

  const logout = async () => {
    const token = localStorage.getItem('session_token');
    if (!token) return;

    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
    } finally {
      localStorage.removeItem('session_token');
      localStorage.removeItem('csrf_token');
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{
      user,
      isLoading,
      isAuthenticated: !!user,
      login,
      logout,
      checkAuth
    }}>
      {children}
    </AuthContext.Provider>
  );
};
```

#### Protected Route Component
```typescript
const ProtectedRoute = ({
  children,
  requiredRole = 'user'
}: {
  children: ReactNode;
  requiredRole?: 'user' | 'admin';
}) => {
  const { user, isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole === 'admin' && user?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
```

#### User Menu Component
```typescript
const UserMenu = () => {
  const { user, logout } = useAuth();
  const [showMenu, setShowMenu] = useState(false);

  if (!user) {
    return (
      <Link to="/login" className="login-button">
        Sign In
      </Link>
    );
  }

  return (
    <div className="user-menu">
      <button
        className="user-avatar"
        onClick={() => setShowMenu(!showMenu)}
      >
        {user.email[0].toUpperCase()}
      </button>

      {showMenu && (
        <div className="user-dropdown">
          <div className="user-info">
            <p>{user.email}</p>
            {user.patreon_tier && (
              <span className="tier-badge">{user.patreon_tier}</span>
            )}
          </div>

          {user.role === 'admin' && (
            <Link to="/admin">Admin Panel</Link>
          )}

          <button onClick={logout}>Sign Out</button>
        </div>
      )}
    </div>
  );
};
```

#### OAuth Callback Handler
```typescript
const OAuthCallback = () => {
  const navigate = useNavigate();
  const { checkAuth } = useAuth();

  useEffect(() => {
    // Extract session data from URL params
    const params = new URLSearchParams(window.location.search);
    const sessionToken = params.get('session_token');
    const csrfToken = params.get('csrf_token');

    if (sessionToken && csrfToken) {
      // Store tokens
      localStorage.setItem('session_token', sessionToken);
      localStorage.setItem('csrf_token', csrfToken);

      // Refresh auth state
      checkAuth().then(() => {
        // Redirect to original destination or home
        const returnTo = localStorage.getItem('auth_return_to') || '/';
        localStorage.removeItem('auth_return_to');
        navigate(returnTo);
      });
    } else {
      // Handle error
      navigate('/login?error=oauth_failed');
    }
  }, []);

  return <LoadingSpinner message="Completing sign in..." />;
};
```

## Implementation Timeline

### Week 1: Database and OAuth Backend ✅
1. Create database migration (version_12.py)
2. Implement OAuth services (Patreon and Google)
3. Create session management enhancements
4. Write OAuth flow endpoints
5. Test OAuth integrations

### Week 2: User Management Backend ✅
1. Implement user service with CRUD operations
2. Create user management API endpoints
3. Add user blocking functionality
4. Implement session revocation
5. Write comprehensive tests

### Week 3: Frontend Components 🔧
1. Create auth context and provider
2. Build login page component
3. Implement protected routes
4. Create user menu component
5. Add OAuth callback handler
6. Integrate auth throughout app

### Week 4: Integration and Polish 🔧
1. Update existing endpoints for RBAC
2. Test end-to-end auth flows
3. Add error handling and edge cases
4. Performance optimization
5. Security audit
6. Documentation updates

## Security Considerations

### Implemented Security Measures ✅
- **Secure token generation**: Using secrets.token_urlsafe(32)
- **Token hashing**: SHA-256 hashing of session tokens in database
- **CSRF protection**: Separate CSRF tokens for state-changing operations
- **Session expiration**: 30-day expiration with automatic cleanup
- **Rate limiting**: Throttled last_used_at updates (1 hour minimum)
- **Blocked user handling**: Sessions invalidated on user block
- **Constant-time comparisons**: For API key and token validation

### Frontend Security Requirements 🔧
- **Secure token storage**: localStorage with HttpOnly cookie fallback
- **XSS prevention**: Sanitize all user-generated content
- **CSRF token handling**: Include in all state-changing requests
- **Logout on 401**: Clear tokens and redirect to login
- **Session timeout warning**: Notify users before expiration

## Success Criteria

### Technical Requirements
- ✅ OAuth integration works reliably with both providers
- ✅ Patreon tier detection accurately maps membership levels
- ✅ Session management handles expiration and revocation properly
- ✅ User blocking immediately invalidates all sessions
- ✅ CSRF protection prevents cross-site attacks
- ✅ Admin users can manage all user accounts
- 🔧 Existing endpoints accept session authentication
- 🔧 Frontend provides smooth authentication experience

### User Experience Requirements
- ✅ OAuth flow completes in under 5 seconds
- ✅ Clear error messages for authentication failures
- 🔧 Seamless session persistence across page reloads
- 🔧 Intuitive login interface with provider choice
- 🔧 Visible user status and tier information
- 🔧 Graceful handling of expired sessions

### Performance Requirements
- ✅ Session validation under 50ms
- ✅ OAuth callback processing under 500ms
- ✅ User list queries optimized with indexes
- 🔧 Frontend auth checks don't block UI
- 🔧 Minimal impact on page load times

## Integration Points

### With Existing Systems
- **Blueprint/Tag APIs**: Add session auth support alongside API keys
- **Documentation System**: Leverage existing session table
- **Image Management**: Extend admin endpoints with session auth
- **Frontend Router**: Add auth guards to protected routes

### External Services
- **Patreon API v2**: Member tier detection via campaigns endpoint
- **Google OAuth 2.0**: Standard OpenID Connect flow
- **Future: Discord OAuth**: Prepared for community integration

## Future Enhancements (Phase 6+)

### API Key Management UI
- User-specific API keys for automation
- Key rotation and expiration
- Usage tracking and rate limiting

### Enhanced User Profiles
- Avatar support
- Display preferences
- Collection management
- Download history

### Social Features
- User-generated collections
- Blueprint ratings and reviews
- Community showcases
- Creator following

### Advanced RBAC
- Granular permissions system
- Custom roles (moderator, creator)
- Feature flags per tier
- Beta access management

This implementation plan captures the substantial progress made on the authentication system while clearly outlining the remaining frontend work needed to complete Phase 5.
