--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13
-- Dumped by pg_dump version 15.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: vpn_user
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO vpn_user;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: vpn_user
--

COMMENT ON SCHEMA public IS '';


--
-- Name: autopaymentstatus; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.autopaymentstatus AS ENUM (
    'INACTIVE',
    'ACTIVE',
    'PAUSED',
    'CANCELLED',
    'FAILED'
);


ALTER TYPE public.autopaymentstatus OWNER TO vpn_user;

--
-- Name: nodemode; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.nodemode AS ENUM (
    'reality'
);


ALTER TYPE public.nodemode OWNER TO vpn_user;

--
-- Name: payment_provider_status; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.payment_provider_status AS ENUM (
    'active',
    'inactive',
    'testing',
    'error',
    'maintenance'
);


ALTER TYPE public.payment_provider_status OWNER TO vpn_user;

--
-- Name: payment_provider_type; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.payment_provider_type AS ENUM (
    'robokassa',
    'yookassa',
    'coingate',
    'paypal',
    'stripe',
    'sberbank',
    'tinkoff',
    'freekassa'
);


ALTER TYPE public.payment_provider_type OWNER TO vpn_user;

--
-- Name: paymentmethod; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.paymentmethod AS ENUM (
    'YOOKASSA_CARD',
    'YOOKASSA_SBP',
    'YOOKASSA_WALLET',
    'COINGATE_CRYPTO',
    'robokassa',
    'freekassa',
    'manual_admin',
    'manual_trial',
    'auto_trial',
    'manual_correction'
);


ALTER TYPE public.paymentmethod OWNER TO vpn_user;

--
-- Name: paymentstatus; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.paymentstatus AS ENUM (
    'PENDING',
    'PROCESSING',
    'SUCCEEDED',
    'FAILED',
    'CANCELLED',
    'REFUNDED'
);


ALTER TYPE public.paymentstatus OWNER TO vpn_user;

--
-- Name: recurringstatus; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.recurringstatus AS ENUM (
    'INACTIVE',
    'ACTIVE',
    'PAUSED',
    'CANCELLED',
    'FAILED'
);


ALTER TYPE public.recurringstatus OWNER TO vpn_user;

--
-- Name: retryresult; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.retryresult AS ENUM (
    'SUCCESS',
    'FAILED',
    'PENDING'
);


ALTER TYPE public.retryresult OWNER TO vpn_user;

--
-- Name: subscriptionstatus; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.subscriptionstatus AS ENUM (
    'ACTIVE',
    'EXPIRED',
    'SUSPENDED',
    'CANCELLED'
);


ALTER TYPE public.subscriptionstatus OWNER TO vpn_user;

--
-- Name: subscriptiontype; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.subscriptiontype AS ENUM (
    'TRIAL',
    'MONTHLY',
    'QUARTERLY',
    'YEARLY'
);


ALTER TYPE public.subscriptiontype OWNER TO vpn_user;

--
-- Name: user_subscription_status; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.user_subscription_status AS ENUM (
    'none',
    'active',
    'expired',
    'suspended'
);


ALTER TYPE public.user_subscription_status OWNER TO vpn_user;

--
-- Name: usersubscriptionstatus; Type: TYPE; Schema: public; Owner: vpn_user
--

CREATE TYPE public.usersubscriptionstatus AS ENUM (
    'NONE',
    'ACTIVE',
    'EXPIRED',
    'SUSPENDED'
);


ALTER TYPE public.usersubscriptionstatus OWNER TO vpn_user;

--
-- Name: update_app_settings_updated_at(); Type: FUNCTION; Schema: public; Owner: vpn_user
--

CREATE FUNCTION public.update_app_settings_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_app_settings_updated_at() OWNER TO vpn_user;

--
-- Name: update_expired_subscriptions(); Type: FUNCTION; Schema: public; Owner: vpn_user
--

CREATE FUNCTION public.update_expired_subscriptions() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE users 
    SET subscription_status = 'expired'
    WHERE subscription_status = 'active' 
    AND subscription_end_date < NOW();
END;
$$;


ALTER FUNCTION public.update_expired_subscriptions() OWNER TO vpn_user;

--
-- Name: FUNCTION update_expired_subscriptions(); Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON FUNCTION public.update_expired_subscriptions() IS 'Функция для обновления истекших подписок';


--
-- Name: update_payment_providers_updated_at(); Type: FUNCTION; Schema: public; Owner: vpn_user
--

CREATE FUNCTION public.update_payment_providers_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_payment_providers_updated_at() OWNER TO vpn_user;

--
-- Name: user_has_valid_subscription(integer); Type: FUNCTION; Schema: public; Owner: vpn_user
--

CREATE FUNCTION public.user_has_valid_subscription(user_id_param integer) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM users 
        WHERE id = user_id_param 
        AND subscription_status = 'active' 
        AND valid_until > NOW()
    );
END;
$$;


ALTER FUNCTION public.user_has_valid_subscription(user_id_param integer) OWNER TO vpn_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.app_settings (
    id integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    site_name character varying(255) DEFAULT 'VPN Service'::character varying NOT NULL,
    site_domain character varying(255),
    site_description text,
    trial_enabled boolean DEFAULT true NOT NULL,
    trial_days integer DEFAULT 7 NOT NULL,
    trial_max_per_user integer DEFAULT 1 NOT NULL,
    token_expire_minutes integer DEFAULT 30 NOT NULL,
    admin_telegram_ids text DEFAULT '[]'::text NOT NULL,
    admin_usernames text DEFAULT '[]'::text NOT NULL,
    telegram_bot_token character varying(255),
    bot_welcome_message text,
    bot_help_message text,
    bot_apps_message text DEFAULT 'Скачайте приложения для вашего устройства:'::text,
    CONSTRAINT app_settings_id_check CHECK ((id = 1)),
    CONSTRAINT app_settings_token_expire_minutes_check CHECK ((token_expire_minutes > 0)),
    CONSTRAINT app_settings_trial_days_check CHECK ((trial_days >= 0)),
    CONSTRAINT app_settings_trial_max_per_user_check CHECK ((trial_max_per_user >= 0))
);


ALTER TABLE public.app_settings OWNER TO vpn_user;

--
-- Name: auto_payments; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.auto_payments (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer NOT NULL,
    payment_id integer NOT NULL,
    robokassa_recurring_id character varying,
    amount double precision NOT NULL,
    currency character varying(3) DEFAULT 'RUB'::character varying,
    period_days integer NOT NULL,
    next_payment_date timestamp without time zone NOT NULL,
    status public.autopaymentstatus DEFAULT 'ACTIVE'::public.autopaymentstatus,
    attempts_count integer DEFAULT 0,
    last_attempt_date timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    last_error_type character varying(50),
    is_recurring_id_valid boolean DEFAULT true
);


ALTER TABLE public.auto_payments OWNER TO vpn_user;

--
-- Name: auto_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.auto_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auto_payments_id_seq OWNER TO vpn_user;

--
-- Name: auto_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.auto_payments_id_seq OWNED BY public.auto_payments.id;


--
-- Name: countries; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.countries (
    id integer NOT NULL,
    code character varying(2) NOT NULL,
    name character varying(100) NOT NULL,
    name_en character varying(100),
    flag_emoji character varying(10) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.countries OWNER TO vpn_user;

--
-- Name: countries_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.countries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.countries_id_seq OWNER TO vpn_user;

--
-- Name: countries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.countries_id_seq OWNED BY public.countries.id;


--
-- Name: payment_providers; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.payment_providers (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    provider_type public.payment_provider_type NOT NULL,
    status public.payment_provider_status DEFAULT 'inactive'::public.payment_provider_status,
    is_active boolean DEFAULT false,
    is_test_mode boolean DEFAULT true,
    is_default boolean DEFAULT false,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    description text,
    webhook_url character varying(500),
    priority integer DEFAULT 100,
    min_amount numeric(10,2) DEFAULT 0.0,
    max_amount numeric(10,2),
    commission_percent numeric(5,2) DEFAULT 0.0,
    commission_fixed numeric(10,2) DEFAULT 0.0,
    total_payments integer DEFAULT 0,
    successful_payments integer DEFAULT 0,
    failed_payments integer DEFAULT 0,
    total_amount numeric(15,2) DEFAULT 0.0,
    last_test_at timestamp with time zone,
    last_test_status character varying(50),
    last_test_message text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    success_url character varying(500),
    failure_url character varying(500),
    notification_url character varying(500),
    notification_method character varying(10) DEFAULT 'POST'::character varying,
    CONSTRAINT chk_payment_providers_amounts CHECK (((min_amount >= (0)::numeric) AND ((max_amount IS NULL) OR (max_amount >= min_amount)))),
    CONSTRAINT chk_payment_providers_commission CHECK (((commission_percent >= (0)::numeric) AND (commission_percent <= (100)::numeric))),
    CONSTRAINT chk_payment_providers_stats CHECK (((total_payments >= 0) AND (successful_payments >= 0) AND (failed_payments >= 0) AND (total_amount >= (0)::numeric))),
    CONSTRAINT payment_providers_notification_method_check CHECK (((notification_method)::text = ANY (ARRAY[('GET'::character varying)::text, ('POST'::character varying)::text])))
);


ALTER TABLE public.payment_providers OWNER TO vpn_user;

--
-- Name: TABLE payment_providers; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON TABLE public.payment_providers IS 'Таблица платежных провайдеров для системы управления платежными системами';


--
-- Name: COLUMN payment_providers.is_default; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payment_providers.is_default IS 'Является ли провайдер основным для нового типа платежей';


--
-- Name: COLUMN payment_providers.config; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payment_providers.config IS 'JSON конфигурация с настройками для каждого типа провайдера';


--
-- Name: COLUMN payment_providers.webhook_url; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payment_providers.webhook_url IS 'URL для получения webhook уведомлений от провайдера';


--
-- Name: COLUMN payment_providers.priority; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payment_providers.priority IS 'Приоритет провайдера для сортировки (меньше = выше приоритет)';


--
-- Name: COLUMN payment_providers.last_test_status; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payment_providers.last_test_status IS 'Статус последнего тестирования (success, error, timeout)';


--
-- Name: payment_providers_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.payment_providers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.payment_providers_id_seq OWNER TO vpn_user;

--
-- Name: payment_providers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.payment_providers_id_seq OWNED BY public.payment_providers.id;


--
-- Name: payment_retry_attempts; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.payment_retry_attempts (
    id integer NOT NULL,
    auto_payment_id integer NOT NULL,
    attempt_number integer NOT NULL,
    error_type character varying NOT NULL,
    error_message text,
    scheduled_at timestamp without time zone NOT NULL,
    attempted_at timestamp without time zone,
    result character varying,
    next_attempt_at timestamp without time zone,
    user_notified boolean DEFAULT false,
    robokassa_response text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.payment_retry_attempts OWNER TO vpn_user;

--
-- Name: payment_retry_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.payment_retry_attempts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.payment_retry_attempts_id_seq OWNER TO vpn_user;

--
-- Name: payment_retry_attempts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.payment_retry_attempts_id_seq OWNED BY public.payment_retry_attempts.id;


--
-- Name: payments; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.payments (
    id integer NOT NULL,
    user_id integer,
    subscription_id integer,
    external_id character varying(255),
    amount double precision NOT NULL,
    currency character varying(3),
    status public.paymentstatus,
    payment_method public.paymentmethod NOT NULL,
    payment_system_data text,
    confirmation_url character varying(500),
    external_payment_id character varying(255),
    external_data json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    paid_at timestamp with time zone,
    processed_at timestamp with time zone,
    description character varying(500),
    failure_reason character varying(500),
    payment_metadata json,
    robokassa_invoice_id character varying(255),
    robokassa_signature character varying(255),
    robokassa_payment_method character varying(100),
    provider_id integer,
    robokassa_recurring_id character varying,
    is_recurring_enabled boolean DEFAULT false,
    recurring_period_days integer,
    next_payment_date timestamp without time zone,
    recurring_status character varying DEFAULT 'inactive'::character varying,
    is_recurring_setup boolean DEFAULT false,
    is_autopay_generated boolean DEFAULT false,
    autopay_attempt_number integer,
    autopay_parent_payment_id integer
);


ALTER TABLE public.payments OWNER TO vpn_user;

--
-- Name: COLUMN payments.robokassa_invoice_id; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payments.robokassa_invoice_id IS 'ID инвойса от Робокассы';


--
-- Name: COLUMN payments.robokassa_signature; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payments.robokassa_signature IS 'Подпись для проверки от Робокассы';


--
-- Name: COLUMN payments.robokassa_payment_method; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.payments.robokassa_payment_method IS 'Метод оплаты в Робокассе';


--
-- Name: payments_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.payments_id_seq OWNER TO vpn_user;

--
-- Name: payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.payments_id_seq OWNED BY public.payments.id;


--
-- Name: server_switch_log; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.server_switch_log (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    from_node_id integer,
    to_node_id integer NOT NULL,
    country_code character varying(2) NOT NULL,
    success boolean DEFAULT false NOT NULL,
    error_message text,
    processing_time_ms integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.server_switch_log OWNER TO vpn_user;

--
-- Name: server_switch_log_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.server_switch_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_switch_log_id_seq OWNER TO vpn_user;

--
-- Name: server_switch_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.server_switch_log_id_seq OWNED BY public.server_switch_log.id;


--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.subscriptions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_type public.subscriptiontype NOT NULL,
    status public.subscriptionstatus,
    price numeric(10,2) NOT NULL,
    currency character varying(3),
    start_date timestamp with time zone DEFAULT now(),
    end_date timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    auto_renewal boolean,
    notes text,
    next_billing_date timestamp without time zone,
    recurring_id character varying,
    recurring_status character varying
);


ALTER TABLE public.subscriptions OWNER TO vpn_user;

--
-- Name: subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.subscriptions_id_seq OWNER TO vpn_user;

--
-- Name: subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.subscriptions_id_seq OWNED BY public.subscriptions.id;


--
-- Name: user_node_assignments; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.user_node_assignments (
    id integer NOT NULL,
    user_id integer NOT NULL,
    node_id integer NOT NULL,
    assigned_at timestamp with time zone DEFAULT now(),
    is_active boolean,
    xui_inbound_id integer,
    xui_client_email character varying(255)
);


ALTER TABLE public.user_node_assignments OWNER TO vpn_user;

--
-- Name: user_node_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.user_node_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_node_assignments_id_seq OWNER TO vpn_user;

--
-- Name: user_node_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.user_node_assignments_id_seq OWNED BY public.user_node_assignments.id;


--
-- Name: user_notification_preferences; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.user_notification_preferences (
    id integer NOT NULL,
    user_id integer NOT NULL,
    notification_type character varying NOT NULL,
    enabled boolean DEFAULT true,
    frequency character varying,
    quiet_hours_start time without time zone,
    quiet_hours_end time without time zone
);


ALTER TABLE public.user_notification_preferences OWNER TO vpn_user;

--
-- Name: user_notification_preferences_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.user_notification_preferences_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_notification_preferences_id_seq OWNER TO vpn_user;

--
-- Name: user_notification_preferences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.user_notification_preferences_id_seq OWNED BY public.user_notification_preferences.id;


--
-- Name: user_server_assignments; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.user_server_assignments (
    user_id bigint NOT NULL,
    node_id integer NOT NULL,
    country_id integer NOT NULL,
    assigned_at timestamp with time zone DEFAULT now(),
    last_switch_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.user_server_assignments OWNER TO vpn_user;

--
-- Name: users; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.users (
    id integer NOT NULL,
    telegram_id bigint NOT NULL,
    username character varying(255),
    first_name character varying(255),
    last_name character varying(255),
    language_code character varying(10),
    is_active boolean,
    is_blocked boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_activity timestamp with time zone DEFAULT now(),
    referrer_id integer,
    referral_code character varying(20),
    subscription_status public.user_subscription_status DEFAULT 'none'::public.user_subscription_status,
    valid_until timestamp with time zone,
    autopay_enabled boolean DEFAULT true
);


ALTER TABLE public.users OWNER TO vpn_user;

--
-- Name: COLUMN users.subscription_status; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.users.subscription_status IS 'Статус аккаунта: active, expired, none';


--
-- Name: COLUMN users.valid_until; Type: COMMENT; Schema: public; Owner: vpn_user
--

COMMENT ON COLUMN public.users.valid_until IS 'Дата окончания действия аккаунта пользователя';


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO vpn_user;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vpn_keys; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.vpn_keys (
    id integer NOT NULL,
    user_id integer NOT NULL,
    node_id integer,
    uuid character varying(36) NOT NULL,
    key_name character varying(255),
    vless_url text NOT NULL,
    vless_config text,
    qr_code_data text,
    status character varying(20),
    xui_email character varying(255) NOT NULL,
    xui_client_id character varying(255),
    xui_inbound_id integer,
    total_download integer,
    total_upload integer,
    last_connection timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone
);


ALTER TABLE public.vpn_keys OWNER TO vpn_user;

--
-- Name: vpn_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.vpn_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.vpn_keys_id_seq OWNER TO vpn_user;

--
-- Name: vpn_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.vpn_keys_id_seq OWNED BY public.vpn_keys.id;


--
-- Name: vpn_nodes; Type: TABLE; Schema: public; Owner: vpn_user
--

CREATE TABLE public.vpn_nodes (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    location character varying(100),
    x3ui_url character varying(255) NOT NULL,
    x3ui_username character varying(100) NOT NULL,
    x3ui_password character varying(255) NOT NULL,
    mode public.nodemode NOT NULL,
    public_key text,
    short_id character varying(32),
    sni_mask character varying(255),
    max_users integer,
    current_users integer,
    status character varying(50),
    last_health_check timestamp with time zone,
    health_status character varying(50),
    response_time_ms integer,
    priority integer,
    weight double precision,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    reality_config jsonb,
    country_id integer
);


ALTER TABLE public.vpn_nodes OWNER TO vpn_user;

--
-- Name: vpn_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: vpn_user
--

CREATE SEQUENCE public.vpn_nodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.vpn_nodes_id_seq OWNER TO vpn_user;

--
-- Name: vpn_nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vpn_user
--

ALTER SEQUENCE public.vpn_nodes_id_seq OWNED BY public.vpn_nodes.id;


--
-- Name: auto_payments id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.auto_payments ALTER COLUMN id SET DEFAULT nextval('public.auto_payments_id_seq'::regclass);


--
-- Name: countries id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.countries ALTER COLUMN id SET DEFAULT nextval('public.countries_id_seq'::regclass);


--
-- Name: payment_providers id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payment_providers ALTER COLUMN id SET DEFAULT nextval('public.payment_providers_id_seq'::regclass);


--
-- Name: payment_retry_attempts id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payment_retry_attempts ALTER COLUMN id SET DEFAULT nextval('public.payment_retry_attempts_id_seq'::regclass);


--
-- Name: payments id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payments ALTER COLUMN id SET DEFAULT nextval('public.payments_id_seq'::regclass);


--
-- Name: server_switch_log id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.server_switch_log ALTER COLUMN id SET DEFAULT nextval('public.server_switch_log_id_seq'::regclass);


--
-- Name: subscriptions id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.subscriptions ALTER COLUMN id SET DEFAULT nextval('public.subscriptions_id_seq'::regclass);


--
-- Name: user_node_assignments id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_node_assignments ALTER COLUMN id SET DEFAULT nextval('public.user_node_assignments_id_seq'::regclass);


--
-- Name: user_notification_preferences id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_notification_preferences ALTER COLUMN id SET DEFAULT nextval('public.user_notification_preferences_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vpn_keys id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.vpn_keys ALTER COLUMN id SET DEFAULT nextval('public.vpn_keys_id_seq'::regclass);


--
-- Name: vpn_nodes id; Type: DEFAULT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.vpn_nodes ALTER COLUMN id SET DEFAULT nextval('public.vpn_nodes_id_seq'::regclass);


--
-- Data for Name: app_settings; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.app_settings (id, created_at, updated_at, site_name, site_domain, site_description, trial_enabled, trial_days, trial_max_per_user, token_expire_minutes, admin_telegram_ids, admin_usernames, telegram_bot_token, bot_welcome_message, bot_help_message, bot_apps_message) FROM stdin;
1	2025-07-21 02:37:06.885253+00	2025-07-23 10:28:38.581488+00	VPN Без лагов	localhost:8000		t	10	1	30	["352313872"]	["av_nosov", "seo2seo"]	8019787780:AAGy5cBWpQ09yvtDE3sp0AMY7kZyRYbSJqU	приветики		Скачайте приложения для вашего устройства:
\.


--
-- Data for Name: auto_payments; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.auto_payments (id, user_id, subscription_id, payment_id, robokassa_recurring_id, amount, currency, period_days, next_payment_date, status, attempts_count, last_attempt_date, created_at, updated_at, last_error_type, is_recurring_id_valid) FROM stdin;
\.


--
-- Data for Name: countries; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.countries (id, code, name, name_en, flag_emoji, is_active, priority, created_at) FROM stdin;
1	RU	Россия	Russia	🇷🇺	t	100	2025-07-19 10:03:50.600813+00
2	NL	Нидерланды	Netherlands	🇳🇱	t	90	2025-07-19 10:03:50.600813+00
3	DE	Германия	Germany	🇩🇪	t	80	2025-07-19 10:03:50.600813+00
\.


--
-- Data for Name: payment_providers; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.payment_providers (id, name, provider_type, status, is_active, is_test_mode, is_default, config, description, webhook_url, priority, min_amount, max_amount, commission_percent, commission_fixed, total_payments, successful_payments, failed_payments, total_amount, last_test_at, last_test_status, last_test_message, created_at, updated_at, success_url, failure_url, notification_url, notification_method) FROM stdin;
2	Test FreeKassa Provider	freekassa	inactive	f	t	f	{"api_key": "39373edd80c7cf6a29e12b0155291b09", "secret1": "_&1)CVzRk)f@fQX", "secret2": "q+aybF3I}ymm}SQ)", "test_mode": true, "merchant_id": "63286", "confirmation_mode": true}	Тестовый провайдер FreeKassa с новыми полями	https://example.com/webhooks/freekassa	100	50.00	50000.00	2.50	0.00	0	0	0	0.00	\N	\N	\N	2025-07-07 16:15:56.935461+00	2025-07-08 19:41:04.492038+00	https://example.com/payment/success	https://example.com/payment/failure	http://localhost:8000/api/v1/webhooks/freekassa	POST
1	Основная Робокасса	robokassa	active	t	t	t	{"shop_id": "bezlagov", "base_url": "https://auth.robokassa.ru/Merchant/Index.aspx", "password1": "KXS28SKL9y5V9NVQiRSG", "password2": "ITixW86d0piZmf7FB1KV"}	Основной провайдер Робокасса для обработки платежей	\N	100	1.00	\N	0.00	0.00	52	5	0	1295.00	2025-07-07 05:55:56.610881+00	error	Ошибка тестирования подключения: Processor for provider type PaymentProviderType.robokassa not found	2025-07-06 10:57:42.354407+00	2025-07-08 19:41:15.139634+00	\N	\N	\N	POST
\.


--
-- Data for Name: payment_retry_attempts; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.payment_retry_attempts (id, auto_payment_id, attempt_number, error_type, error_message, scheduled_at, attempted_at, result, next_attempt_at, user_notified, robokassa_response, created_at) FROM stdin;
\.


--
-- Data for Name: payments; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.payments (id, user_id, subscription_id, external_id, amount, currency, status, payment_method, payment_system_data, confirmation_url, external_payment_id, external_data, created_at, updated_at, paid_at, processed_at, description, failure_reason, payment_metadata, robokassa_invoice_id, robokassa_signature, robokassa_payment_method, provider_id, robokassa_recurring_id, is_recurring_enabled, recurring_period_days, next_payment_date, recurring_status, is_recurring_setup, is_autopay_generated, autopay_attempt_number, autopay_parent_payment_id) FROM stdin;
84	\N	\N	84	100	RUB	SUCCEEDED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=84&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=71af7f73371835e15561d9ccea71d22b	\N	\N	2025-07-23 06:26:34.110407+00	2025-07-23 06:28:48.485917+00	2025-07-23 06:26:42.833305+00	2025-07-23 06:26:42.833324+00	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	84	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
60	\N	\N	60	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=60&Description=VPN подписка на 1 месяц&IsTest=1&SignatureValue=b3bc4ce2f1b6883d68e5aae2395704d6	\N	\N	2025-07-10 10:58:25.176482+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN подписка на 1 месяц	\N	{"subscription_type": "monthly", "service_name": null, "duration_days": 30}	60	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
61	\N	\N	61	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=61&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_352313872%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=66652a231e3e34b2052a1af1cd0273ec	\N	\N	2025-07-10 11:01:09.054811+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	61	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
63	\N	\N	63	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=63&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=cddb45bc4f697fcc7251115614da2eb4	\N	\N	2025-07-15 01:42:31.473354+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	63	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
52	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:37:48.103283+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Premium	\N	{"subscription_type": "monthly", "service_name": "VPN Premium", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
55	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:39:46.631251+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Premium	\N	{"subscription_type": "monthly", "service_name": "VPN Premium", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
64	\N	\N	64	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=64&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_352313872%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=12e1424d7db30346ea1c24ea3a279da1	\N	\N	2025-07-16 03:10:42.015291+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	64	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
1	\N	\N	1	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=1&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=9b1009c1989963d814a695ea71a1dbc6	\N	\N	2025-07-07 14:32:21.959382+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	1	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
2	\N	\N	2	300	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=300.0&InvId=2&Description=На 90 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=b5109e62c1764152b4443fe3f5ef2071	\N	\N	2025-07-07 14:33:02.359337+00	2025-07-21 02:06:54.582755+00	\N	\N	На 90 дней	\N	{"subscription_type": "quarterly", "service_name": "\\u041d\\u0430 90 \\u0434\\u043d\\u0435\\u0439", "duration_days": 90}	2	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
53	\N	\N	53	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=53&Description=VPN Premium&IsTest=1&SignatureValue=23cf7df5c79e965a10e156f254919299	\N	\N	2025-07-08 19:38:13.616879+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Premium	\N	{"subscription_type": "monthly", "service_name": "VPN Premium", "duration_days": 30}	53	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
13	\N	\N	13	100	RUB	SUCCEEDED	freekassa	\N	https://pay.freekassa.ru/?shopId=39373edd80c7cf6a29e12b0155291b09&sum=100.0&orderid=13&desc=VPN подписка на 1 месяц&currency=RUB&email=test@example.com&success_url=https://example.com/payment/success&failure_url=https://example.com/payment/failure&notification_url=https://example.com/webhooks/freekassa&sign=4c39e16d82b179dce6c5f7ae9402594d	\N	\N	2025-07-08 06:11:54.01239+00	2025-07-21 02:06:54.582755+00	2025-07-08 06:12:05.675723+00	2025-07-08 06:12:05.675728+00	VPN подписка на 1 месяц	\N	{"subscription_type": "monthly", "service_name": null, "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
32	\N	\N	32	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=32&us_desc=VPN Месячная подписка для теста webhook&currency=RUB&us_email=test@example.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=https://example.com/webhooks/freekassa&s=54190d1d1a3b1e13e0978b727133c529	\N	\N	2025-07-08 18:48:06.993686+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка для теста webhook	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430 \\u0434\\u043b\\u044f \\u0442\\u0435\\u0441\\u0442\\u0430 webhook", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
7	\N	\N	7	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=7&Description=VPN Месячная подписка FreeKassa Test v2&IsTest=1&Email=test@example.com&SuccessURL=https://example.com/success&FailURL=https://example.com/fail&SignatureValue=868d0958eaf17b5acf1ac20cebc691b3	\N	\N	2025-07-07 19:22:36.971242+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка FreeKassa Test v2	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430 FreeKassa Test v2", "duration_days": 30}	7	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
8	\N	\N	8	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=8&Description=VPN FreeKassa FINAL TEST&IsTest=1&Email=test@example.com&SuccessURL=https://example.com/success&FailURL=https://example.com/fail&SignatureValue=b4402a00cc53b9182873354203a21f0d	\N	\N	2025-07-07 19:23:44.299046+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN FreeKassa FINAL TEST	\N	{"subscription_type": "monthly", "service_name": "VPN FreeKassa FINAL TEST", "duration_days": 30}	8	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
10	\N	\N	10	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?shopId=39373edd80c7cf6a29e12b0155291b09&sum=100.0&orderid=10&desc=VPN подписка на 1 месяц&currency=RUB&email=test@example.com&success_url=https://example.com/payment/success&failure_url=https://example.com/payment/failure&notification_url=https://example.com/webhooks/freekassa&sign=f907a7872affe7a95934f928e9c2fb19	\N	\N	2025-07-07 19:29:50.857645+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN подписка на 1 месяц	\N	{"subscription_type": "monthly", "service_name": null, "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
11	\N	\N	11	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=11&Description=VPN подписка на 1 месяц&IsTest=1&Email=test@example.com&SignatureValue=23e20af9f9cb3897296bef117105a594	\N	\N	2025-07-07 19:31:28.414364+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN подписка на 1 месяц	\N	{"subscription_type": "monthly", "service_name": null, "duration_days": 30, "provider_type": "robokassa"}	11	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
56	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:40:53.720576+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
85	\N	\N	85	100	RUB	SUCCEEDED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=85&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_352313872%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=8b899769903ca1c8b13a2a2df1f03861	\N	\N	2025-07-23 06:29:14.596261+00	2025-07-23 06:50:12.171785+00	2025-07-23 06:29:40.757489+00	2025-07-23 06:29:40.757514+00	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	85	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
67	\N	\N	67	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=67&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_1266460617%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=e9ac7d807f512f143ec96e7e3a84e367	\N	\N	2025-07-18 11:18:38.646774+00	2025-07-23 07:05:15.167782+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	67	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
15	\N	\N	15	300	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?shopId=39373edd80c7cf6a29e12b0155291b09&sum=300.0&orderid=15&desc=VPN подписка на 3 месяца&currency=RUB&email=final-test@example.com&success_url=https://example.com/payment/success&failure_url=https://example.com/payment/failure&notification_url=https://example.com/webhooks/freekassa&sign=5a41a68e9aed82c8451f99363e1197d2	\N	\N	2025-07-08 06:13:53.453661+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN подписка на 3 месяца	\N	{"subscription_type": "quarterly", "service_name": null, "duration_days": 90, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
16	\N	\N	16	300	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=300.0&InvId=16&Description=VPN подписка на 3 месяца&IsTest=1&Email=final-test@example.com&SignatureValue=74f491f3c8e2b6ed6f127ec766620033	\N	\N	2025-07-08 06:14:24.160669+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN подписка на 3 месяца	\N	{"subscription_type": "quarterly", "service_name": null, "duration_days": 90, "provider_type": "robokassa"}	16	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
51	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:35:47.074838+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
49	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:32:49.369616+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Premium	\N	{"subscription_type": "monthly", "service_name": "VPN Premium", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
21	\N	\N	21	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=21&us_desc=На 30 дней&currency=RUB&us_email=user_352313872@telegram.local&us_success=https://t.me/vpn_bezlagov_test_bot?start=payment_success&us_fail=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&us_notification=https://example.com/webhooks/freekassa&s=c1047b15452339642c5344554bf5f4bb	\N	\N	2025-07-08 07:26:29.816681+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
23	\N	\N	\N	600	RUB	CANCELLED	robokassa	\N	\N	\N	\N	2025-07-08 10:18:13.802909+00	2025-07-21 02:06:54.582755+00	\N	\N	На 180 дней	\N	{"subscription_type": "semi_annual", "service_name": "\\u041d\\u0430 180 \\u0434\\u043d\\u0435\\u0439", "duration_days": 180}	\N	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
24	\N	\N	24	300	RUB	SUCCEEDED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=300.0&InvId=24&Description=На 90 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=2387fb5581e66eb92b066ca2948b43d8	\N	{"OutSum": "300.0", "InvId": "24", "SignatureValue": "test_signature_for_debugging"}	2025-07-08 10:20:21.208128+00	2025-07-21 02:06:54.582755+00	2025-07-08 10:27:10.743615+00	2025-07-08 10:27:10.74362+00	На 90 дней	\N	{"subscription_type": "quarterly", "service_name": "\\u041d\\u0430 90 \\u0434\\u043d\\u0435\\u0439", "duration_days": 90}	24	test_signature_for_debugging	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
26	\N	\N	\N	0	RUB	SUCCEEDED	manual_admin	\N	\N	\N	\N	2025-07-08 11:50:40.643324+00	2025-07-21 02:06:54.582755+00	2025-07-08 11:59:17.420847+00	2025-07-08 11:59:17.420857+00	тест	\N	{"subscription_days": 10}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
25	\N	\N	25	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=25&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=432c62eab5bcaa0fd2ba73b556c70aa1	\N	\N	2025-07-08 10:35:30.211828+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	25	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
28	\N	\N	28	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=28&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=58c4e95dbf9bb375a274cb4aaccb7726	\N	\N	2025-07-08 18:22:23.847957+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	28	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
29	\N	\N	29	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=29&us_desc=VPN Месячная подписка&currency=RUB&us_email=test@example.com&us_success=https://example.com/success&us_fail=https://example.com/fail&us_notification=https://example.com/webhooks/freekassa&s=b4b8ce6ad3cea587c7925a2db6f83bfc	\N	\N	2025-07-08 18:47:46.74746+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
30	\N	\N	30	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=30&us_desc=VPN Месячная подписка&currency=RUB&us_email=test@example.com&us_success=https://example.com/success&us_fail=https://example.com/fail&us_notification=https://example.com/webhooks/freekassa&s=5a1df80cf9f94d0cea8596fc8afffdd8	\N	\N	2025-07-08 18:47:54.480407+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
31	\N	\N	31	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=31&us_desc=На 30 дней&currency=RUB&us_email=user_352313872@telegram.local&us_success=https://t.me/vpn_bezlagov_test_bot?start=payment_success&us_fail=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&us_notification=https://example.com/webhooks/freekassa&s=9bbd72b8cada67cdd118189bc4bdd846	\N	\N	2025-07-08 18:48:00.681804+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
33	\N	\N	33	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=33&us_desc=VPN Месячная подписка - тест FreeKassa&currency=RUB&us_email=test@example.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=https://example.com/webhooks/freekassa&s=e9886f466b82f5a21f449bedabc741d7	\N	\N	2025-07-08 18:50:35.102799+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка - тест FreeKassa	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430 - \\u0442\\u0435\\u0441\\u0442 FreeKassa", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
34	\N	\N	34	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=34&us_desc=VPN Месячная подписка - ФИНАЛЬНЫЙ ТЕСТ&currency=RUB&us_email=test@example.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=354df19c95b7b0e0ae28e7aae7d9dc64	\N	\N	2025-07-08 18:54:06.118457+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка - ФИНАЛЬНЫЙ ТЕСТ	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430 - \\u0424\\u0418\\u041d\\u0410\\u041b\\u042c\\u041d\\u042b\\u0419 \\u0422\\u0415\\u0421\\u0422", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
17	\N	\N	17	100	RUB	SUCCEEDED	freekassa	\N	https://pay.freekassa.ru/?shopId=39373edd80c7cf6a29e12b0155291b09&sum=100.0&orderid=17&desc=VPN Monthly Test Auto Provider&currency=RUB&email=test@example.com&success_url=https://example.com/payment/success&failure_url=https://example.com/payment/failure&notification_url=https://example.com/webhooks/freekassa&sign=6e71a405516f320e132747ec8a7f6f61	\N	\N	2025-07-08 06:34:01.633007+00	2025-07-21 02:06:54.582755+00	2025-07-08 06:34:44.166384+00	2025-07-08 06:34:44.16639+00	VPN Monthly Test Auto Provider	\N	{"subscription_type": "monthly", "service_name": "VPN Monthly Test Auto Provider", "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
18	\N	\N	18	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?shopId=39373edd80c7cf6a29e12b0155291b09&sum=100.0&orderid=18&desc=На 30 дней&currency=RUB&email=user_352313872@telegram.local&success_url=https://t.me/vpn_bezlagov_test_bot?start=payment_success&failure_url=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&notification_url=https://example.com/webhooks/freekassa&sign=c21af866ad24cab2f77269028aa04c9c	\N	\N	2025-07-08 06:46:44.096899+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
19	\N	\N	19	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=19&us_desc=VPN Monthly Test&currency=RUB&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=https://example.com/webhooks/freekassa&s=18a3d45c070dce991b95c14e7d8cfee7	\N	\N	2025-07-08 06:56:02.156491+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Monthly Test	\N	{"subscription_type": "monthly", "service_name": "VPN Monthly Test", "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
57	\N	\N	57	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=57&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=799cb6b9469df3247e83e2758f420736	\N	\N	2025-07-08 19:41:22.676942+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	57	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
20	\N	\N	20	100	RUB	CANCELLED	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=20&us_desc=На 30 дней&currency=RUB&us_email=user_352313872@telegram.local&us_success=https://t.me/vpn_bezlagov_test_bot?start=payment_success&us_fail=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&us_notification=https://example.com/webhooks/freekassa&s=a500b07aee540ca57e639c6b00b771e2	\N	\N	2025-07-08 06:56:07.636189+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
58	\N	\N	58	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=58&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=d95ed1a8597c2783cccd167647ba4d0b	\N	\N	2025-07-08 20:06:17.471714+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	58	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
86	\N	\N	\N	100	RUB	SUCCEEDED	manual_admin	\N	\N	\N	\N	2025-07-23 06:33:29.88341+00	2025-07-23 06:50:12.171785+00	2025-07-23 06:33:35.610733+00	2025-07-23 06:33:35.610763+00	Месячная подписка VPN	\N	{"subscription_days": 30}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
88	\N	\N	88	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=88&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_352313872%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=ffe3536f83bf261c3b85a6245c31244f	\N	\N	2025-07-23 06:52:49.864046+00	2025-07-23 07:24:38.97001+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	88	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
41	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:06:38.039052+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN - ИСПРАВЛЕННЫЙ ТЕСТ FREEKASSA	\N	{"subscription_type": "monthly", "service_name": "VPN - \\u0418\\u0421\\u041f\\u0420\\u0410\\u0412\\u041b\\u0415\\u041d\\u041d\\u042b\\u0419 \\u0422\\u0415\\u0421\\u0422 FREEKASSA", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
54	\N	\N	54	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=54&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=950b0dc33be6e5afae06fec526e8ae18	\N	\N	2025-07-08 19:39:32.329553+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	54	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
12	\N	\N	12	100	RUB	FAILED	freekassa	\N	https://pay.freekassa.ru/?shopId=39373edd80c7cf6a29e12b0155291b09&sum=100.0&orderid=12&desc=VPN подписка на 1 месяц&currency=RUB&email=test@example.com&success_url=https://example.com/payment/success&failure_url=https://example.com/payment/failure&notification_url=https://example.com/webhooks/freekassa&sign=1b1453111edf64d969d6c1945fca2a2e	\N	\N	2025-07-08 06:09:53.672654+00	2025-07-21 02:06:54.582755+00	\N	2025-07-08 06:10:06.853432+00	VPN подписка на 1 месяц	Payment failed in FreeKassa	{"subscription_type": "monthly", "service_name": null, "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
14	\N	\N	14	100	RUB	SUCCEEDED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=14&Description=VPN подписка на 1 месяц&IsTest=1&Email=test@example.com&SignatureValue=1027077ec64a83511a1c23e9c4fa2f22	\N	{"OutSum": "100.0", "InvId": "14", "SignatureValue": "bc57293a4b7e09b16cdc85f1e42f943e"}	2025-07-08 06:12:24.287569+00	2025-07-21 02:06:54.582755+00	2025-07-08 06:12:36.738204+00	2025-07-08 06:12:36.738207+00	VPN подписка на 1 месяц	\N	{"subscription_type": "monthly", "service_name": null, "duration_days": 30, "provider_type": "robokassa"}	14	bc57293a4b7e09b16cdc85f1e42f943e	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
9	\N	\N	9	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=9&Description=VPN подписка на 1 месяц&IsTest=1&Email=test@example.com&SignatureValue=400361675b12c3d97186a117877a95c6	\N	\N	2025-07-07 19:27:05.891161+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN подписка на 1 месяц	\N	{"subscription_type": "monthly", "service_name": null, "duration_days": 30}	9	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
3	\N	\N	3	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=3&Description=VPN Месячная подписка&IsTest=1&Email=test@example.com&SuccessURL=https://example.com/success&FailURL=https://example.com/fail&SignatureValue=f79f1f89bf72fbd8847696ff926fdfb3	\N	\N	2025-07-07 19:19:13.570279+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430", "duration_days": 30}	3	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
35	\N	\N	35	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=35&us_desc=VPN - Финальный тест системы&currency=RUB&us_email=final@test.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=218dc07dcbc76b7648c7d3410d647d50	\N	\N	2025-07-08 18:56:20.536177+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN - Финальный тест системы	\N	{"subscription_type": "monthly", "service_name": "VPN - \\u0424\\u0438\\u043d\\u0430\\u043b\\u044c\\u043d\\u044b\\u0439 \\u0442\\u0435\\u0441\\u0442 \\u0441\\u0438\\u0441\\u0442\\u0435\\u043c\\u044b", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
38	\N	\N	38	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=38&us_desc=ТЕСТ - проверка домена в ссылке&currency=RUB&us_email=domain@test.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=50b5d96bfc5e12bcc40d82687e002f3b	\N	\N	2025-07-08 19:00:20.447968+00	2025-07-21 02:06:54.582755+00	\N	\N	ТЕСТ - проверка домена в ссылке	\N	{"subscription_type": "monthly", "service_name": "\\u0422\\u0415\\u0421\\u0422 - \\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u043a\\u0430 \\u0434\\u043e\\u043c\\u0435\\u043d\\u0430 \\u0432 \\u0441\\u0441\\u044b\\u043b\\u043a\\u0435", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
75	\N	\N	75	100	RUB	SUCCEEDED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=75&Description=На 30 дней&IsTest=1&Email=user_352313872@telegram.local&SuccessURL=https://t.me/vpn_bezlagov_test_bot?start=payment_success&FailURL=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&SignatureValue=8483670d809fe69aba2f282a8bd92f1a	\N	\N	2025-07-23 01:44:29.937745+00	2025-07-23 01:55:39.248762+00	2025-07-23 01:49:56.148344+00	2025-07-23 01:49:56.148395+00	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	75	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
79	\N	\N	\N	100	RUB	SUCCEEDED	manual_admin	\N	\N	\N	\N	2025-07-23 01:51:07.675779+00	2025-07-23 01:55:39.248762+00	2025-07-23 01:51:16.906206+00	2025-07-23 01:51:16.906222+00	Месячная подписка VPN	\N	{"subscription_days": 30}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
87	\N	\N	87	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=87&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_352313872%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=d6ef70a404b291ba7445da46ca4412f2	\N	\N	2025-07-23 06:52:18.099431+00	2025-07-23 07:24:38.97001+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	87	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
89	\N	\N	89	100	RUB	PENDING	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=89&Description=%D0%9D%D0%B0+30+%D0%B4%D0%BD%D0%B5%D0%B9&Recurring=true&IsTest=1&Email=user_1266460617%40telegram.local&SuccessURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_success&FailURL=https%3A%2F%2Ft.me%2Fvpn_bezlagov_test_bot%3Fstart%3Dpayment_fail&SignatureValue=3fd88af48e1a6d2a1633333afae8d2dd	\N	\N	2025-07-23 07:15:21.799041+00	2025-07-23 07:26:12.60959+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	89	\N	\N	1	\N	t	30	\N	INACTIVE	t	f	\N	\N
90	34	\N	\N	0	RUB	SUCCEEDED	auto_trial	\N	\N	\N	\N	2025-07-23 07:24:51.704813+00	2025-07-23 07:24:51.714689+00	2025-07-23 07:24:51.714094+00	2025-07-23 07:24:51.714107+00	Автоматический триальный период - 10 дней	\N	{}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
91	35	\N	\N	0	RUB	SUCCEEDED	auto_trial	\N	\N	\N	\N	2025-07-23 07:29:59.953697+00	2025-07-23 07:29:59.957676+00	2025-07-23 07:29:59.957329+00	2025-07-23 07:29:59.957338+00	Автоматический триальный период - 10 дней	\N	{}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
4	\N	\N	4	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=4&Description=VPN Месячная подписка&IsTest=1&Email=test@example.com&SuccessURL=https://example.com/success&FailURL=https://example.com/fail&SignatureValue=0cdbfa4eacc600b752bf63e1e82ecdbc	\N	\N	2025-07-07 19:19:59.471558+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430", "duration_days": 30}	4	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
5	\N	\N	5	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=5&Description=VPN Месячная подписка&IsTest=1&Email=test@example.com&SuccessURL=https://example.com/success&FailURL=https://example.com/fail&SignatureValue=8e0ca9ea13cf40aef074e480fdc860eb	\N	\N	2025-07-07 19:20:27.985565+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430", "duration_days": 30}	5	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
6	\N	\N	6	100	RUB	CANCELLED	robokassa	\N	https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=bezlagov&OutSum=100.0&InvId=6&Description=VPN Месячная подписка FreeKassa Test&IsTest=1&Email=test@example.com&SuccessURL=https://example.com/success&FailURL=https://example.com/fail&SignatureValue=3981e6ff1227c66f80b4ff42de0e4919	\N	\N	2025-07-07 19:21:14.817619+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Месячная подписка FreeKassa Test	\N	{"subscription_type": "monthly", "service_name": "VPN \\u041c\\u0435\\u0441\\u044f\\u0447\\u043d\\u0430\\u044f \\u043f\\u043e\\u0434\\u043f\\u0438\\u0441\\u043a\\u0430 FreeKassa Test", "duration_days": 30}	6	\N	\N	1	\N	f	\N	\N	INACTIVE	f	f	\N	\N
80	\N	\N	\N	0	RUB	SUCCEEDED	auto_trial	\N	\N	\N	\N	2025-07-23 01:55:52.003556+00	2025-07-23 05:59:18.11676+00	2025-07-23 01:55:52.012648+00	2025-07-23 01:55:52.012663+00	Автоматический триальный период - 3 дней	\N	{}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
22	2	\N	22	100	RUB	PENDING	freekassa	\N	https://pay.freekassa.ru/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=22&us_desc=На 30 дней&currency=RUB&us_email=user_374817873@telegram.local&us_success=https://t.me/vpn_bezlagov_test_bot?start=payment_success&us_fail=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&us_notification=https://example.com/webhooks/freekassa&s=cbae89c807bc72f51c762a45122c9585	\N	\N	2025-07-08 08:29:00.59033+00	2025-07-08 08:29:00.593921+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30, "provider_type": "freekassa"}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
81	\N	\N	\N	0	RUB	SUCCEEDED	auto_trial	\N	\N	\N	\N	2025-07-23 05:59:22.618031+00	2025-07-23 06:02:29.587307+00	2025-07-23 05:59:22.630975+00	2025-07-23 05:59:22.630989+00	Автоматический триальный период - 3 дней	\N	{}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
27	\N	\N	\N	0	RUB	SUCCEEDED	manual_admin	\N	\N	\N	\N	2025-07-08 11:51:45.655257+00	2025-07-21 02:06:54.582755+00	2025-07-08 11:51:52.033952+00	2025-07-08 11:51:52.034+00	тест	\N	{"subscription_days": 10}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
82	\N	\N	\N	0	RUB	SUCCEEDED	auto_trial	\N	\N	\N	\N	2025-07-23 06:06:43.051713+00	2025-07-23 06:09:11.811717+00	2025-07-23 06:06:43.066979+00	2025-07-23 06:06:43.066992+00	Автоматический триальный период - 3 дней	\N	{}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
36	\N	\N	36	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=36&us_desc=На 30 дней&currency=RUB&us_email=user_352313872@telegram.local&us_success=https://t.me/vpn_bezlagov_test_bot?start=payment_success&us_fail=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=41c32012870ccd3ae906058ff8c4eb14	\N	\N	2025-07-08 18:56:45.278951+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
37	\N	\N	37	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=37&us_desc=Тест проверки ссылки&currency=RUB&us_email=test@example.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=d91d67943bdc0ad6a713c1089ddb1845	\N	\N	2025-07-08 18:57:52.854232+00	2025-07-21 02:06:54.582755+00	\N	\N	Тест проверки ссылки	\N	{"subscription_type": "monthly", "service_name": "\\u0422\\u0435\\u0441\\u0442 \\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u043a\\u0438 \\u0441\\u0441\\u044b\\u043b\\u043a\\u0438", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
39	\N	\N	39	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=39&us_desc=Финальный тест&currency=RUB&us_email=test@final.com&us_success=https://example.com/payment/success&us_fail=https://example.com/payment/failure&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=7c3b7e033b7a4557e94da61a677a255f	\N	\N	2025-07-08 19:01:08.181579+00	2025-07-21 02:06:54.582755+00	\N	\N	Финальный тест	\N	{"subscription_type": "monthly", "service_name": "\\u0424\\u0438\\u043d\\u0430\\u043b\\u044c\\u043d\\u044b\\u0439 \\u0442\\u0435\\u0441\\u0442", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
40	\N	\N	40	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=39373edd80c7cf6a29e12b0155291b09&oa=100.0&o=40&us_desc=На 30 дней&currency=RUB&us_email=user_352313872@telegram.local&us_success=https://t.me/vpn_bezlagov_test_bot?start=payment_success&us_fail=https://t.me/vpn_bezlagov_test_bot?start=payment_fail&us_notification=http://localhost:8000/api/v1/webhooks/freekassa&s=3b50c3ec35716331798469f67e81107e	\N	\N	2025-07-08 19:01:47.350756+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
42	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:07:06.032241+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN - ИСПРАВЛЕННЫЙ ТЕСТ FREEKASSA	\N	{"subscription_type": "monthly", "service_name": "VPN - \\u0418\\u0421\\u041f\\u0420\\u0410\\u0412\\u041b\\u0415\\u041d\\u041d\\u042b\\u0419 \\u0422\\u0415\\u0421\\u0422 FREEKASSA", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
43	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:07:36.875709+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN - ФИНАЛЬНЫЙ ТЕСТ FREEKASSA	\N	{"subscription_type": "monthly", "service_name": "VPN - \\u0424\\u0418\\u041d\\u0410\\u041b\\u042c\\u041d\\u042b\\u0419 \\u0422\\u0415\\u0421\\u0422 FREEKASSA", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
44	\N	\N	44	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=1234567&oa=100.0&o=44&currency=RUB&em=final%40test.com&s=10192aa3651855d4fc896d1b37dafd5e	\N	\N	2025-07-08 19:08:26.479944+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN - ОКОНЧАТЕЛЬНЫЙ ТЕСТ FREEKASSA	\N	{"subscription_type": "monthly", "service_name": "VPN - \\u041e\\u041a\\u041e\\u041d\\u0427\\u0410\\u0422\\u0415\\u041b\\u042c\\u041d\\u042b\\u0419 \\u0422\\u0415\\u0421\\u0422 FREEKASSA", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
45	\N	\N	45	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=1234567&oa=100.0&o=45&currency=RUB&em=system%40test.com&s=b980544c0d9418894bff28e2cfa00fa0	\N	\N	2025-07-08 19:09:07.147128+00	2025-07-21 02:06:54.582755+00	\N	\N	СИСТЕМНЫЙ ТЕСТ - FreeKassa работает!	\N	{"subscription_type": "monthly", "service_name": "\\u0421\\u0418\\u0421\\u0422\\u0415\\u041c\\u041d\\u042b\\u0419 \\u0422\\u0415\\u0421\\u0422 - FreeKassa \\u0440\\u0430\\u0431\\u043e\\u0442\\u0430\\u0435\\u0442!", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
46	\N	\N	46	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=1234567&oa=100.0&o=46&currency=RUB&em=user_352313872%40telegram.local&s=01ae0510eeba85c5812762f8e540a8e1	\N	\N	2025-07-08 19:10:22.806269+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
47	\N	\N	47	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=1234567&oa=100.0&o=47&currency=RUB&s=e1dddb1d725cfe52cdb016cdf88911dc	\N	\N	2025-07-08 19:14:29.329642+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Premium	\N	{"subscription_type": "monthly", "service_name": "VPN Premium", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
48	\N	\N	48	100	RUB	CANCELLED	freekassa	\N	https://pay.fk.money/?m=1234567&oa=100.0&o=48&currency=RUB&em=user_352313872%40telegram.local&s=5e8720bc5d01d5775aff6a89da14f290	\N	\N	2025-07-08 19:27:27.827306+00	2025-07-21 02:06:54.582755+00	\N	\N	На 30 дней	\N	{"subscription_type": "monthly", "service_name": "\\u041d\\u0430 30 \\u0434\\u043d\\u0435\\u0439", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
50	\N	\N	\N	100	RUB	CANCELLED	freekassa	\N	\N	\N	\N	2025-07-08 19:34:36.8957+00	2025-07-21 02:06:54.582755+00	\N	\N	VPN Premium	\N	{"subscription_type": "monthly", "service_name": "VPN Premium", "duration_days": 30}	\N	\N	\N	2	\N	f	\N	\N	INACTIVE	f	f	\N	\N
83	\N	\N	\N	0	RUB	SUCCEEDED	auto_trial	\N	\N	\N	\N	2025-07-23 06:09:37.925861+00	2025-07-23 06:12:04.415606+00	2025-07-23 06:09:37.932886+00	2025-07-23 06:09:37.932895+00	Автоматический триальный период - 3 дней	\N	{}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
92	34	\N	\N	1	RUB	SUCCEEDED	manual_admin	\N	\N	\N	\N	2025-07-29 07:06:16.798483+00	2025-07-29 07:06:22.054476+00	2025-07-29 07:06:22.052974+00	2025-07-29 07:06:22.053006+00	Месячная подписка VPN	\N	{"subscription_days": 30}	\N	\N	\N	\N	\N	f	\N	\N	INACTIVE	f	f	\N	\N
\.


--
-- Data for Name: server_switch_log; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.server_switch_log (id, user_id, from_node_id, to_node_id, country_code, success, error_message, processing_time_ms, created_at) FROM stdin;
42	352313872	5	5	DE	t	\N	8	2025-07-28 04:57:58.900901+00
\.


--
-- Data for Name: subscriptions; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.subscriptions (id, user_id, subscription_type, status, price, currency, start_date, end_date, created_at, updated_at, auto_renewal, notes, next_billing_date, recurring_id, recurring_status) FROM stdin;
\.


--
-- Data for Name: user_node_assignments; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.user_node_assignments (id, user_id, node_id, assigned_at, is_active, xui_inbound_id, xui_client_email) FROM stdin;
\.


--
-- Data for Name: user_notification_preferences; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.user_notification_preferences (id, user_id, notification_type, enabled, frequency, quiet_hours_start, quiet_hours_end) FROM stdin;
\.


--
-- Data for Name: user_server_assignments; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.user_server_assignments (user_id, node_id, country_id, assigned_at, last_switch_at) FROM stdin;
352313872	5	3	2025-07-28 04:57:58.897154+00	2025-07-28 04:57:58.897154+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.users (id, telegram_id, username, first_name, last_name, language_code, is_active, is_blocked, created_at, updated_at, last_activity, referrer_id, referral_code, subscription_status, valid_until, autopay_enabled) FROM stdin;
2	374817873	tanosova7	Tanya ☘️	\N	ru	t	f	2025-07-08 08:28:14.678121+00	2025-07-08 08:28:14.678121+00	2025-07-08 08:28:14.678121+00	\N	\N	active	2025-07-15 08:28:14.678446+00	t
5	205866953	zehya	Evgeny	\N	ru	t	f	2025-07-12 10:02:24.713453+00	2025-07-12 10:02:24.713453+00	2025-07-12 10:02:24.713453+00	\N	\N	active	2025-07-19 10:02:24.714031+00	t
20	999999	testuser	Test	\N	ru	t	f	2025-07-23 06:12:41.248321+00	2025-07-23 06:12:41.248321+00	2025-07-23 06:12:41.248321+00	\N	\N	active	2025-08-22 06:12:41.25649+00	t
21	999998	testuser2	Test2	\N	ru	t	f	2025-07-23 06:12:50.653784+00	2025-07-23 06:12:50.653784+00	2025-07-23 06:12:50.653784+00	\N	\N	none	\N	t
23	999997	testuser3	Test3	\N	ru	t	f	2025-07-23 06:16:53.988189+00	2025-07-23 06:16:53.988189+00	2025-07-23 06:16:53.988189+00	\N	\N	active	2025-08-22 06:16:53.998719+00	t
24	999996	testuser4	Test4	\N	ru	t	f	2025-07-23 06:17:37.995797+00	2025-07-23 06:17:37.995797+00	2025-07-23 06:17:37.995797+00	\N	\N	active	2025-08-22 06:17:38.007574+00	t
25	999995	testuser5	Test5	\N	ru	t	f	2025-07-23 06:18:47.855606+00	2025-07-23 06:18:47.855606+00	2025-07-23 06:18:47.855606+00	\N	\N	active	2025-08-22 06:18:47.867693+00	t
26	999994	testuser6	Test6	\N	ru	t	f	2025-07-23 06:19:06.245239+00	2025-07-23 06:19:06.245239+00	2025-07-23 06:19:06.245239+00	\N	\N	active	2025-08-22 06:19:06.246156+00	t
27	999993	testuser7	Test7	\N	ru	t	f	2025-07-23 06:19:38.977163+00	2025-07-23 06:19:38.977163+00	2025-07-23 06:19:38.977163+00	\N	\N	none	\N	t
28	999992	testuser8	Test8	\N	ru	t	f	2025-07-23 06:19:45.613041+00	2025-07-23 06:19:45.613041+00	2025-07-23 06:19:45.613041+00	\N	\N	none	\N	t
29	999991	testuser9	Test9	\N	ru	t	f	2025-07-23 06:19:49.942526+00	2025-07-23 06:19:49.942526+00	2025-07-23 06:19:49.942526+00	\N	\N	none	\N	t
35	1266460617	seo2seo	Эмиль	\N	ru	t	f	2025-07-23 07:29:59.948216+00	2025-07-23 07:30:15.07945+00	2025-07-23 07:29:59.948216+00	\N	\N	active	2025-08-05 07:29:59.948543+00	f
34	352313872	av_nosov	Andrey	\N	ru	t	f	2025-07-23 07:24:51.692898+00	2025-07-29 07:06:22.044796+00	2025-07-23 07:24:51.692898+00	\N	\N	active	2025-09-04 07:24:51.693386+00	f
36	123456789	test_user	Test	User	ru	t	f	2025-07-30 09:17:19.823566+00	2025-07-30 09:17:19.823566+00	2025-07-30 09:17:19.823566+00	\N	\N	active	2025-08-29 09:17:19.831484+00	t
\.


--
-- Data for Name: vpn_keys; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.vpn_keys (id, user_id, node_id, uuid, key_name, vless_url, vless_config, qr_code_data, status, xui_email, xui_client_id, xui_inbound_id, total_download, total_upload, last_connection, created_at, updated_at, expires_at) FROM stdin;
165	20	4	0b84e0e7-f27e-42c9-ab08-04e61f7756a2	vpn_key_user_999999_1753251161	vless://0b84e0e7-f27e-42c9-ab08-04e61f7756a2@78.40.193.142:443?type=tcp&security=reality&fp=chrome&pbk=jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU&sni=apple.com&flow=xtls-rprx-vision&sid=ef21f59c&spx=%2F#999999_1753251163	\N	\N	active	999999_1753251163	0b84e0e7-f27e-42c9-ab08-04e61f7756a2	1	0	0	\N	2025-07-23 06:12:41.260617+00	2025-07-23 06:12:41.260617+00	\N
168	24	5	b5bd2b94-c4a3-41eb-8500-718159138634	vpn_key_user_999996_1753251458	vless://b5bd2b94-c4a3-41eb-8500-718159138634@185.157.214.239:443?type=tcp&security=reality&fp=chrome&pbk=RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o&sni=apple.com&flow=xtls-rprx-vision&sid=51f4992b&spx=%2F#999996_1753251460	\N	\N	active	999996_1753251460	b5bd2b94-c4a3-41eb-8500-718159138634	1	0	0	\N	2025-07-23 06:17:38.012858+00	2025-07-23 06:17:38.012858+00	\N
15	2	1	30d71fe1-e930-4f1d-a637-0e4a63612b66	updated_key_374817873_1751963359	vless://30d71fe1-e930-4f1d-a637-0e4a63612b66@78.40.193.142:443?type=tcp&security=reality&fp=chrome&pbk=jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU&sni=apple.com&flow=xtls-rprx-vision&sid=ef21f59c&spx=%2F#374817873_1751963359 (Tanya ☘️)@vpn.local	\N	\N	ACTIVE	374817873 (Tanya ☘️)	30d71fe1-e930-4f1d-a637-0e4a63612b66	1	0	0	\N	2025-07-08 08:29:19.212089+00	2025-07-08 08:29:19.212089+00	\N
167	23	5	50d1b32f-8a86-4fbc-b8c7-5bf1d579a233	vpn_key_user_999997_1753251414	vless://50d1b32f-8a86-4fbc-b8c7-5bf1d579a233@185.157.214.239:443?type=tcp&security=reality&fp=chrome&pbk=RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o&sni=apple.com&flow=xtls-rprx-vision&sid=51f4992b&spx=%2F#999997_1753251416	\N	\N	active	999997_1753251416	50d1b32f-8a86-4fbc-b8c7-5bf1d579a233	1	0	0	\N	2025-07-23 06:16:54.00308+00	2025-07-23 06:16:54.00308+00	\N
169	25	4	1ea54e25-fb22-4466-aa17-9f982a140121	vpn_key_user_999995_1753251527	vless://1ea54e25-fb22-4466-aa17-9f982a140121@78.40.193.142:443?type=tcp&security=reality&fp=chrome&pbk=jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU&sni=apple.com&flow=xtls-rprx-vision&sid=ef21f59c&spx=%2F#999995_1753251530	\N	\N	active	999995_1753251530	1ea54e25-fb22-4466-aa17-9f982a140121	1	0	0	\N	2025-07-23 06:18:47.874655+00	2025-07-23 06:18:47.874655+00	\N
170	26	5	c1acda49-1f38-498d-961b-6d5c25555468	vpn_key_user_999994_1753251546	vless://c1acda49-1f38-498d-961b-6d5c25555468@185.157.214.239:443?type=tcp&security=reality&fp=chrome&pbk=RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o&sni=apple.com&flow=xtls-rprx-vision&sid=51f4992b&spx=%2F#999994_1753251548	\N	\N	active	999994_1753251548	c1acda49-1f38-498d-961b-6d5c25555468	1	0	0	\N	2025-07-23 06:19:06.250822+00	2025-07-23 06:19:06.250822+00	\N
176	35	4	6b30010c-66ed-41be-9022-4c67e0cfbf8d	vpn_key_user_1266460617_1753255800	vless://6b30010c-66ed-41be-9022-4c67e0cfbf8d@78.40.193.142:443?type=tcp&security=reality&fp=chrome&pbk=jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU&sni=apple.com&flow=xtls-rprx-vision&sid=ef21f59c&spx=%2F#1266460617_1753255802	\N	\N	active	1266460617_1753255802	6b30010c-66ed-41be-9022-4c67e0cfbf8d	1	0	0	\N	2025-07-23 07:30:00.620511+00	2025-07-23 07:30:00.620511+00	\N
34	5	4	0e412ced-c0be-4238-8ed1-45b97dcbade7	vpn_key_user_205866953_1752314544	vless://0e412ced-c0be-4238-8ed1-45b97dcbade7@78.40.193.142:443?type=tcp&security=reality&fp=chrome&pbk=jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU&sni=apple.com&flow=xtls-rprx-vision&sid=ef21f59c&spx=%2F#205866953_1752314547	\N	\N	active	205866953_1752314547	0e412ced-c0be-4238-8ed1-45b97dcbade7	1	0	0	\N	2025-07-12 10:02:24.732586+00	2025-07-12 10:02:24.732586+00	\N
178	34	5	1e73452c-223c-4df8-bc0f-29157455e626	key_1753678691	vless://1e73452c-223c-4df8-bc0f-29157455e626@185.157.214.239:443?type=tcp&security=reality&fp=chrome&pbk=RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o&sni=apple.com&flow=xtls-rprx-vision&sid=51f4992b&spx=%2F#352313872_1753678689 (Andrey)@vpn.local	\N	\N	active	352313872_1753678689 (Andrey)@vpn.local	1e73452c-223c-4df8-bc0f-29157455e626	1	0	0	\N	2025-07-28 04:58:11.437149+00	2025-07-28 04:58:11.437149+00	\N
179	36	5	b7583cdb-b668-4434-863a-ff535c83c744	vpn_key_user_123456789_1753867039	vless://b7583cdb-b668-4434-863a-ff535c83c744@185.157.214.239:443?type=tcp&security=reality&fp=chrome&pbk=RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o&sni=apple.com&flow=xtls-rprx-vision&sid=51f4992b&spx=%2F#123456789_1753867040	\N	\N	active	123456789_1753867040	b7583cdb-b668-4434-863a-ff535c83c744	1	0	0	\N	2025-07-30 09:17:19.838059+00	2025-07-30 09:17:19.838059+00	\N
180	36	4	f8acd998-9dcd-4913-aefe-b2afbc20ecd7	vpn_key_user_123456789_1753867051	vless://f8acd998-9dcd-4913-aefe-b2afbc20ecd7@78.40.193.142:443?type=tcp&security=reality&fp=chrome&pbk=jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU&sni=apple.com&flow=xtls-rprx-vision&sid=ef21f59c&spx=%2F#123456789_1753867051	\N	\N	active	123456789_1753867051	f8acd998-9dcd-4913-aefe-b2afbc20ecd7	1	0	0	\N	2025-07-30 09:17:31.254573+00	2025-07-30 09:17:31.254573+00	\N
181	36	5	6bb817d0-abd5-48c7-afe9-1a30596afbc8	vpn_key_user_123456789_1753867101	vless://6bb817d0-abd5-48c7-afe9-1a30596afbc8@185.157.214.239:443?type=tcp&security=reality&fp=chrome&pbk=RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o&sni=apple.com&flow=xtls-rprx-vision&sid=51f4992b&spx=%2F#123456789_1753867102	\N	\N	active	123456789_1753867102	6bb817d0-abd5-48c7-afe9-1a30596afbc8	1	0	0	\N	2025-07-30 09:18:21.478325+00	2025-07-30 09:18:21.478325+00	\N
\.


--
-- Data for Name: vpn_nodes; Type: TABLE DATA; Schema: public; Owner: vpn_user
--

COPY public.vpn_nodes (id, name, description, location, x3ui_url, x3ui_username, x3ui_password, mode, public_key, short_id, sni_mask, max_users, current_users, status, last_health_check, health_status, response_time_ms, priority, weight, created_at, updated_at, reality_config, country_id) FROM stdin;
5	vpn3-2	Auto-deployed Reality node via SSH on 185.157.214.239	Германия	http://185.157.214.239:2053/m9rbjubu8q3q	admin	3k54nal0u9E0	reality	kOfbOXV57C-onwvqy6VtuRRqGZDBSTKxebtEK1KKBgk	038fe58b	apple.com	1000	6	active	2025-08-01 03:25:59.376347+00	healthy	400	100	1	2025-07-15 00:33:23.502845+00	2025-08-01 03:25:58.962842+00	\N	3
3	Test Node	Тестовая VPN нода	Россия	https://bezlagov.ru:2053/KZcdnNax4qgt1CY	admin	2U9Zkb97JKNP3jN9	reality	\N	\N	\N	1000	0	inactive	2025-08-01 03:26:00.018094+00	healthy	623	1	100	2025-07-08 20:03:31.186023+00	2025-08-01 03:25:59.393784+00	\N	1
1	vpn2	Auto-deployed Reality node via SSH on 78.40.193.142	Auto-detected	http://78.40.193.142:2053/nl76r82x9aml	admin	a4XbZqsiktNV	reality	jPxJ0QysDW1DELJQuRfNmOkpuTEQNXTtzIeVvX16mmU	ef21f59c	apple.com	1000	0	inactive	2025-08-01 03:26:00.182246+00	unhealthy	156	100	1	2025-07-07 14:26:09.020096+00	2025-08-01 03:26:00.025126+00	\N	\N
2	vpn3	Auto-deployed Reality node via SSH on 185.157.214.239	Auto-detected	http://185.157.214.239:2053/f8hzmzlfpw1x	admin	5InWhkUfzN5w	reality	RO70Gf5LALIso7zUpqXiIXLw11IwfjS67bmoZMyRz1o	51f4992b	apple.com	1000	0	inactive	2025-08-01 03:26:00.345409+00	unhealthy	153	100	1	2025-07-07 14:28:27.447796+00	2025-08-01 03:26:00.190531+00	\N	\N
4	vpn2-2	Auto-deployed Reality node via SSH on 78.40.193.142	Нидерланды	http://78.40.193.142:2053/04ltsvmxbepr	admin	ZMEfUYCv8dSc	reality	P51EUDYsiPvTIhQvDowKs4Bpm4DRrZzT5VBBjtWlLW4	b29c279b	apple.com	1000	5	active	2025-08-01 03:26:00.734804+00	healthy	381	100	1	2025-07-12 09:57:03.673998+00	2025-08-01 03:26:00.351967+00	\N	2
\.


--
-- Name: auto_payments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.auto_payments_id_seq', 1, false);


--
-- Name: countries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.countries_id_seq', 3, true);


--
-- Name: payment_providers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.payment_providers_id_seq', 2, true);


--
-- Name: payment_retry_attempts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.payment_retry_attempts_id_seq', 1, false);


--
-- Name: payments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.payments_id_seq', 92, true);


--
-- Name: server_switch_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.server_switch_log_id_seq', 42, true);


--
-- Name: subscriptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.subscriptions_id_seq', 1, false);


--
-- Name: user_node_assignments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.user_node_assignments_id_seq', 1, false);


--
-- Name: user_notification_preferences_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.user_notification_preferences_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.users_id_seq', 36, true);


--
-- Name: vpn_keys_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.vpn_keys_id_seq', 181, true);


--
-- Name: vpn_nodes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vpn_user
--

SELECT pg_catalog.setval('public.vpn_nodes_id_seq', 5, true);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (id);


--
-- Name: auto_payments auto_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.auto_payments
    ADD CONSTRAINT auto_payments_pkey PRIMARY KEY (id);


--
-- Name: countries countries_code_key; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_code_key UNIQUE (code);


--
-- Name: countries countries_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_pkey PRIMARY KEY (id);


--
-- Name: payment_providers payment_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payment_providers
    ADD CONSTRAINT payment_providers_pkey PRIMARY KEY (id);


--
-- Name: payment_retry_attempts payment_retry_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payment_retry_attempts
    ADD CONSTRAINT payment_retry_attempts_pkey PRIMARY KEY (id);


--
-- Name: payments pk_payments; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT pk_payments PRIMARY KEY (id);


--
-- Name: subscriptions pk_subscriptions; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT pk_subscriptions PRIMARY KEY (id);


--
-- Name: user_node_assignments pk_user_node_assignments; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_node_assignments
    ADD CONSTRAINT pk_user_node_assignments PRIMARY KEY (id);


--
-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);


--
-- Name: vpn_keys pk_vpn_keys; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.vpn_keys
    ADD CONSTRAINT pk_vpn_keys PRIMARY KEY (id);


--
-- Name: vpn_nodes pk_vpn_nodes; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.vpn_nodes
    ADD CONSTRAINT pk_vpn_nodes PRIMARY KEY (id);


--
-- Name: server_switch_log server_switch_log_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.server_switch_log
    ADD CONSTRAINT server_switch_log_pkey PRIMARY KEY (id);


--
-- Name: user_notification_preferences user_notification_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_notification_preferences
    ADD CONSTRAINT user_notification_preferences_pkey PRIMARY KEY (id);


--
-- Name: user_notification_preferences user_notification_preferences_user_id_key; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_notification_preferences
    ADD CONSTRAINT user_notification_preferences_user_id_key UNIQUE (user_id);


--
-- Name: user_server_assignments user_server_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_server_assignments
    ADD CONSTRAINT user_server_assignments_pkey PRIMARY KEY (user_id);


--
-- Name: idx_countries_code; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_countries_code ON public.countries USING btree (code);


--
-- Name: idx_countries_is_active; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_countries_is_active ON public.countries USING btree (is_active);


--
-- Name: idx_countries_priority; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_countries_priority ON public.countries USING btree (priority);


--
-- Name: idx_payment_providers_active; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payment_providers_active ON public.payment_providers USING btree (is_active, is_default);


--
-- Name: idx_payment_providers_is_active; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payment_providers_is_active ON public.payment_providers USING btree (is_active);


--
-- Name: idx_payment_providers_priority; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payment_providers_priority ON public.payment_providers USING btree (priority);


--
-- Name: idx_payment_providers_provider_type; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payment_providers_provider_type ON public.payment_providers USING btree (provider_type);


--
-- Name: idx_payment_providers_status; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payment_providers_status ON public.payment_providers USING btree (status);


--
-- Name: idx_payment_providers_type_status; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payment_providers_type_status ON public.payment_providers USING btree (provider_type, status);


--
-- Name: idx_payments_provider_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payments_provider_id ON public.payments USING btree (provider_id);


--
-- Name: idx_payments_robokassa_invoice_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_payments_robokassa_invoice_id ON public.payments USING btree (robokassa_invoice_id);


--
-- Name: idx_users_subscription_status; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_users_subscription_status ON public.users USING btree (subscription_status);


--
-- Name: idx_users_telegram_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_users_telegram_id ON public.users USING btree (telegram_id);


--
-- Name: idx_users_valid_until; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_users_valid_until ON public.users USING btree (valid_until);


--
-- Name: idx_vpn_keys_user_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_vpn_keys_user_id ON public.vpn_keys USING btree (user_id);


--
-- Name: idx_vpn_nodes_country_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX idx_vpn_nodes_country_id ON public.vpn_nodes USING btree (country_id);


--
-- Name: ix_payments_external_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_payments_external_id ON public.payments USING btree (external_id);


--
-- Name: ix_payments_external_payment_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_payments_external_payment_id ON public.payments USING btree (external_payment_id);


--
-- Name: ix_payments_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_payments_id ON public.payments USING btree (id);


--
-- Name: ix_subscriptions_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_subscriptions_id ON public.subscriptions USING btree (id);


--
-- Name: ix_user_node_assignments_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_user_node_assignments_id ON public.user_node_assignments USING btree (id);


--
-- Name: ix_user_node_assignments_is_active; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_user_node_assignments_is_active ON public.user_node_assignments USING btree (is_active);


--
-- Name: ix_user_node_assignments_node_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_user_node_assignments_node_id ON public.user_node_assignments USING btree (node_id);


--
-- Name: ix_user_node_assignments_user_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_user_node_assignments_user_id ON public.user_node_assignments USING btree (user_id);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_referral_code; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_users_referral_code ON public.users USING btree (referral_code);


--
-- Name: ix_users_referrer_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_users_referrer_id ON public.users USING btree (referrer_id);


--
-- Name: ix_users_telegram_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_users_telegram_id ON public.users USING btree (telegram_id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: ix_vpn_keys_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_vpn_keys_id ON public.vpn_keys USING btree (id);


--
-- Name: ix_vpn_keys_key_name; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_vpn_keys_key_name ON public.vpn_keys USING btree (key_name);


--
-- Name: ix_vpn_keys_uuid; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_vpn_keys_uuid ON public.vpn_keys USING btree (uuid);


--
-- Name: ix_vpn_keys_xui_client_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_vpn_keys_xui_client_id ON public.vpn_keys USING btree (xui_client_id);


--
-- Name: ix_vpn_keys_xui_email; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_vpn_keys_xui_email ON public.vpn_keys USING btree (xui_email);


--
-- Name: ix_vpn_nodes_id; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE INDEX ix_vpn_nodes_id ON public.vpn_nodes USING btree (id);


--
-- Name: ix_vpn_nodes_name; Type: INDEX; Schema: public; Owner: vpn_user
--

CREATE UNIQUE INDEX ix_vpn_nodes_name ON public.vpn_nodes USING btree (name);


--
-- Name: payment_providers trigger_payment_providers_updated_at; Type: TRIGGER; Schema: public; Owner: vpn_user
--

CREATE TRIGGER trigger_payment_providers_updated_at BEFORE UPDATE ON public.payment_providers FOR EACH ROW EXECUTE FUNCTION public.update_payment_providers_updated_at();


--
-- Name: app_settings update_app_settings_updated_at_trigger; Type: TRIGGER; Schema: public; Owner: vpn_user
--

CREATE TRIGGER update_app_settings_updated_at_trigger BEFORE UPDATE ON public.app_settings FOR EACH ROW EXECUTE FUNCTION public.update_app_settings_updated_at();


--
-- Name: auto_payments auto_payments_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.auto_payments
    ADD CONSTRAINT auto_payments_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: auto_payments auto_payments_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.auto_payments
    ADD CONSTRAINT auto_payments_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: auto_payments auto_payments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.auto_payments
    ADD CONSTRAINT auto_payments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: payments fk_payments_provider_id; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT fk_payments_provider_id FOREIGN KEY (provider_id) REFERENCES public.payment_providers(id) ON DELETE SET NULL;


--
-- Name: payments fk_payments_subscription_id_subscriptions; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT fk_payments_subscription_id_subscriptions FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: payments fk_payments_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT fk_payments_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: subscriptions fk_subscriptions_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT fk_subscriptions_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_node_assignments fk_user_node_assignments_node_id_vpn_nodes; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_node_assignments
    ADD CONSTRAINT fk_user_node_assignments_node_id_vpn_nodes FOREIGN KEY (node_id) REFERENCES public.vpn_nodes(id) ON DELETE CASCADE;


--
-- Name: user_node_assignments fk_user_node_assignments_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.user_node_assignments
    ADD CONSTRAINT fk_user_node_assignments_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vpn_keys fk_vpn_keys_node_id_vpn_nodes; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.vpn_keys
    ADD CONSTRAINT fk_vpn_keys_node_id_vpn_nodes FOREIGN KEY (node_id) REFERENCES public.vpn_nodes(id);


--
-- Name: vpn_keys fk_vpn_keys_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.vpn_keys
    ADD CONSTRAINT fk_vpn_keys_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: payment_retry_attempts payment_retry_attempts_auto_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payment_retry_attempts
    ADD CONSTRAINT payment_retry_attempts_auto_payment_id_fkey FOREIGN KEY (auto_payment_id) REFERENCES public.auto_payments(id);


--
-- Name: payments payments_autopay_parent_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vpn_user
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_autopay_parent_payment_id_fkey FOREIGN KEY (autopay_parent_payment_id) REFERENCES public.payments(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: vpn_user
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;


--
-- PostgreSQL database dump complete
--

