package com.example.catalogservice.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import javax.persistence.EntityNotFoundException;
import javax.servlet.http.HttpServletRequest;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(EntityNotFoundException.class)
    public ResponseEntity<ApiError> handleEntityNotFound(
            EntityNotFoundException ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.NOT_FOUND.value(),
                "Resource Not Found",
                ex.getMessage(),
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiError> handleIllegalArgument(
            IllegalArgumentException ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.BAD_REQUEST.value(),
                "Invalid Request",
                ex.getMessage(),
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(apiError);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationApiError> handleValidationErrors(
            MethodArgumentNotValidException ex,
            HttpServletRequest request) {
        Map<String, String> fieldErrors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach((error) -> {
            String fieldName = ((FieldError) error).getField();
            String errorMessage = error.getDefaultMessage();
            fieldErrors.put(fieldName, errorMessage);
        });

        ValidationApiError apiError = new ValidationApiError(
                HttpStatus.BAD_REQUEST.value(),
                "Validation Error",
                fieldErrors,
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(apiError);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ApiError> handleAccessDenied(
            AccessDeniedException ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.FORBIDDEN.value(),
                "Access Denied",
                "Insufficient permissions to access this resource",
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(apiError);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleGenericException(
            Exception ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.INTERNAL_SERVER_ERROR.value(),
                "Server Error",
                "An unexpected error occurred",
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(apiError);
    }

    // Error response classes
    public static class ApiError {
        private final LocalDateTime timestamp;
        private final int statusCode;
        private final String errorType;
        private final String detail;
        private final String requestPath;

        public ApiError(int statusCode, String errorType, String detail, String requestPath) {
            this.timestamp = LocalDateTime.now();
            this.statusCode = statusCode;
            this.errorType = errorType;
            this.detail = detail;
            this.requestPath = requestPath;
        }

        public LocalDateTime getTimestamp() { return timestamp; }
        public int getStatusCode() { return statusCode; }
        public String getErrorType() { return errorType; }
        public String getDetail() { return detail; }
        public String getRequestPath() { return requestPath; }
    }

    public static class ValidationApiError {
        private final LocalDateTime timestamp;
        private final int statusCode;
        private final String errorType;
        private final Map<String, String> fieldErrors;
        private final String requestPath;

        public ValidationApiError(int statusCode, String errorType, Map<String, String> fieldErrors, String requestPath) {
            this.timestamp = LocalDateTime.now();
            this.statusCode = statusCode;
            this.errorType = errorType;
            this.fieldErrors = fieldErrors;
            this.requestPath = requestPath;
        }

        public LocalDateTime getTimestamp() { return timestamp; }
        public int getStatusCode() { return statusCode; }
        public String getErrorType() { return errorType; }
        public Map<String, String> getFieldErrors() { return fieldErrors; }
        public String getRequestPath() { return requestPath; }
    }
}
