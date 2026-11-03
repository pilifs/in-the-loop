package net.terminalvalue.boxoffice.ticketing.app;

/**
 * The result of an idempotent create.
 *
 * @param created false when the request repeated an earlier one and {@code value} is what that one created
 */
public record Created<T>(T value, boolean created) {}
